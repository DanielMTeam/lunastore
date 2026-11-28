from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.api.authentication import CustomJWTAuthentication
from apps.api.token_sessions import issue_tokens
from apps.api.v3.batch import MAX_BATCH_BYTES
from apps.marketplace.models import Application, Category, Collection, CollectionItem, Distribution, Platform
from apps.user.models import User


@override_settings(ROOT_URLCONF="lunastore.urls_api", MEILISEARCH_ENABLED=False)
class CatalogContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="publisher")
        cls.platform = Platform.objects.create(code="mobile", name="Windows Mobile")
        cls.category = Category.objects.create(name="Utilities", icon="util")
        cls.app = Application.objects.create(user=cls.owner, title="Mobile Cleaner", price=0)
        cls.app.platforms.add(cls.platform)
        cls.app.categories.add(cls.category)
        cls.distribution = Distribution.objects.create(
            app=cls.app, version="1.0", url="https://example.test/cleaner.zip", platform=cls.platform,
        )
        cls.private = Application.objects.create(user=cls.owner, title="Hidden Cleaner", is_private=True)
        cls.collection = Collection.objects.create(owner=cls.owner, title="My apps", is_public=True)
        CollectionItem.objects.create(collection=cls.collection, application=cls.app)

    def test_mobile_catalog_flow(self):
        response = self.client.get("/v3/apps/", {"q": "Cleaner", "platform": "mobile", "is_free": "true"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        app = response.data["results"][0]
        self.assertEqual(app["id"], self.app.pk)
        self.assertEqual(app["platforms"][0]["code"], "mobile")
        self.assertTrue(app["categories"][0]["icon_url"].startswith("https://"))
        distributions = self.client.get(f"/v3/apps/{self.app.pk}/distributions/")
        self.assertEqual(distributions.status_code, 200, distributions.data)
        link = distributions.data["results"][0]["download_url"]
        self.assertEqual(self.client.get(link).status_code, 302)

    def test_collection_owner_filter_and_apps(self):
        response = self.client.get("/v3/collections/", {"user_id": self.owner.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["results"][0]["items_count"], 1)
        apps = self.client.get(f"/v3/collections/{self.collection.pk}/apps/")
        self.assertEqual(apps.data["results"][0]["id"], self.app.pk)

    def test_errors_follow_problem_details(self):
        response = self.client.get("/v3/apps/", {"limit": "101", "author": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/problem+json")
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual({error["path"] for error in response.data["errors"]}, {"limit", "author"})
        response = self.client.get(f"/v3/apps/{self.private.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/problem+json")

    @patch("apps.core.search.SearchService.search_application_ids")
    def test_batch_reuses_results_and_preserves_per_call_status(self, search):
        search.return_value = ([self.app.pk], 2)
        params = {"q": "Cleaner", "platform": "mobile", "limit": 1}
        direct = self.client.get("/v3/apps/", params)
        search.reset_mock()
        calls = [
            {"id": "first", "operation": "v3_apps_list", "params": params},
            {"id": "missing", "operation": "v3_apps_retrieve", "params": {"pk": self.private.pk}},
            {"id": "same", "operation": "v3_apps_list", "params": params},
            {"id": "private", "operation": "v3_me_retrieve"},
        ]
        response = self.client.post("/v3/batch/", {"requests": calls}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        results = response.data["results"]
        self.assertEqual([item["id"] for item in results], ["first", "missing", "same", "private"])
        self.assertEqual([item["status"] for item in results], [200, 404, 200, 400])
        self.assertEqual(results[0]["body"], direct.data)
        self.assertEqual(results[0]["body"], results[2]["body"])
        search.assert_called_once()

    @patch("apps.api.throttling.RealIPAnonRateThrottle.allow_request", return_value=True)
    def test_batch_charges_every_element_to_quota(self, throttle):
        calls = [{"id": str(index), "operation": "v3_platforms_list"} for index in range(3)]
        response = self.client.post("/v3/batch/", {"requests": calls}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(throttle.call_count, 3)

    def test_batch_authenticates_once_and_preserves_private_access(self):
        tokens = issue_tokens(self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        direct = self.client.get(f"/v3/apps/{self.private.pk}/")
        params = {"pk": self.private.pk}
        with patch.object(
            CustomJWTAuthentication, "authenticate", autospec=True,
            side_effect=CustomJWTAuthentication.authenticate,
        ) as authenticate:
            response = self.client.post("/v3/batch/", {"requests": [
                {"id": "one", "operation": "v3_apps_retrieve", "params": params},
                {"id": "two", "operation": "v3_apps_retrieve", "params": params},
            ]}, format="json")
        self.assertEqual(direct.status_code, 200)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["body"] for item in response.data["results"]], [direct.data, direct.data])
        authenticate.assert_called_once()

    @override_settings(LUNASPIRE_URL="//spire.example.test", LUNASPIRE_SECRET_KEY="test-signing-key-for-downloads-32")
    def test_v3_cdn_download_uses_https_and_disables_caching(self):
        self.distribution.cdn_file_id = "42"
        self.distribution.save(update_fields=["cdn_file_id"])
        response = self.client.get(
            f"/v3/distributions/{self.distribution.pk}/download/", HTTP_USER_AGENT="MSIE 6",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://spire.example.test/cdn/download?token="))
        self.assertIn("no-store", response["Cache-Control"])

    def test_batch_rejects_empty_oversized_and_duplicate_ids(self):
        valid = {"id": "same", "operation": "v3_platforms_list"}
        for calls in ([], [valid, valid], [{**valid, "id": str(index)} for index in range(26)]):
            with self.subTest(length=len(calls)):
                response = self.client.post("/v3/batch/", {"requests": calls}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Content-Type"], "application/problem+json")

    def test_batch_rejects_oversized_body_before_json_parsing(self):
        response = self.client.generic("POST", "/v3/batch/", b" " * (MAX_BATCH_BYTES + 1), "application/json")
        self.assertEqual(response.status_code, 413, response.data)
        self.assertEqual(response.data["code"], "batch_too_large")

    @patch("apps.core.search.SearchService.search_application_ids", return_value=([], 0))
    def test_batch_limits_distinct_searches_without_blocking_browse(self, search):
        operations = [
            {"id": str(i), "operation": "v3_apps_list", "params": {"q": query}}
            for i, query in enumerate(("first", "second", "third"))
        ]
        operations.append({"id": "platforms", "operation": "v3_platforms_list"})
        response = self.client.post("/v3/batch/", {"requests": operations}, format="json")
        self.assertEqual([item["status"] for item in response.data["results"]], [200, 200, 400, 200])
        self.assertEqual(response.data["results"][2]["body"]["code"], "batch_search_limit")
        self.assertEqual(search.call_count, 2)

    @patch("apps.api.v3.batch.monotonic")
    def test_batch_stops_new_reads_after_deadline(self, monotonic):
        current_time = 0
        monotonic.side_effect = lambda: current_time

        def search(*args, **kwargs):
            nonlocal current_time
            current_time = 20
            return [], 0

        with patch("apps.core.search.SearchService.search_application_ids", side_effect=search):
            response = self.client.post("/v3/batch/", {"requests": [
                {"id": "search", "operation": "v3_apps_list", "params": {"q": "Cleaner"}},
                {"id": "platforms", "operation": "v3_platforms_list"},
            ]}, format="json")
        self.assertEqual([item["status"] for item in response.data["results"]], [503, 503])
        self.assertEqual({item["body"]["code"] for item in response.data["results"]}, {"batch_timeout"})

    @patch("apps.api.v3.batch.STATEMENT_TIMEOUT_MS", 20)
    def test_batch_sql_timeout_rolls_back_and_keeps_connection_usable(self):
        def search(*args, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_sleep(0.1)")
            return [], 0

        with patch("apps.core.search.SearchService.search_application_ids", side_effect=search):
            response = self.client.post("/v3/batch/", {"requests": [
                {"id": "search", "operation": "v3_apps_list", "params": {"q": "Cleaner"}},
            ]}, format="json")
        item = response.data["results"][0]
        self.assertEqual(item["status"], 503)
        self.assertEqual(item["body"]["code"], "batch_timeout")
        self.assertEqual(self.client.get("/v3/apps/").status_code, 200)

    @override_settings(LUNASPIRE_URL="spire.example.test", API_MEDIA_BASE_URL="https://store.example.test/")
    def test_uploaded_media_stays_on_spire_host(self):
        Application.objects.filter(pk=self.app.pk).update(icon_path="cdn/icon.png", screenshots=["cdn/shot.png"])
        User.objects.filter(pk=self.owner.pk).update(avatar_path="cdn/avatar.png")
        response = self.client.get(f"/v3/apps/{self.app.pk}/")
        self.assertEqual(response.data["icon_url"], "https://spire.example.test/cdn/icon.png")
        self.assertEqual(response.data["screenshot_urls"], ["https://spire.example.test/cdn/shot.png"])
        self.assertEqual(response.data["user"]["avatar_url"], "https://spire.example.test/cdn/avatar.png")

    @patch("apps.core.search.SearchService.search_application_ids")
    def test_catalog_pagination_uses_validated_numbers(self, search):
        params = {"limit": "1.0", "offset": "1.0"}
        browse = self.client.get("/v3/apps/", params)
        self.assertEqual(browse.data["count"], 1)
        self.assertEqual(browse.data["results"], [])
        search.return_value = ([], 1)
        response = self.client.get("/v3/apps/", {"q": "Cleaner", **params})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(search.call_args.kwargs["limit"], 1)
        self.assertEqual(search.call_args.kwargs["offset"], 1)

    @override_settings(API_PUBLIC_SCHEME="https")
    def test_paginated_links_use_configured_public_scheme(self):
        Category.objects.create(name="Games", icon="entertainment")
        for endpoint in ("/v2/category/", "/v3/categories/"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint, {"limit": 1})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.data["next"].startswith(f"https://testserver{endpoint}"))

    def test_batch_reduces_catalog_queries_for_shared_sections(self):
        paths = ("/v3/categories/", "/v3/platforms/", "/v3/categories/")
        operations = ("v3_categories_list", "v3_platforms_list", "v3_categories_list")
        with CaptureQueriesContext(connection) as direct:
            responses = [self.client.get(path) for path in paths]
        with CaptureQueriesContext(connection) as bundled:
            response = self.client.post("/v3/batch/", {
                "requests": [{"id": str(index), "operation": operation} for index, operation in enumerate(operations)],
            }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["body"] for item in response.data["results"]], [item.data for item in responses])

        def catalog_reads(queries):
            return sum(
                query["sql"].startswith("SELECT")
                and "pg_settings" not in query["sql"]
                and "set_config" not in query["sql"]
                for query in queries
            )

        self.assertLess(catalog_reads(bundled), catalog_reads(direct))
        self.assertLess(len(response.content), sum(len(item.content) for item in responses) + 100 * len(operations))
