from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

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

    def test_batch_rejects_empty_oversized_and_duplicate_ids(self):
        valid = {"id": "same", "operation": "v3_platforms_list"}
        for calls in ([], [valid, valid], [{**valid, "id": str(index)} for index in range(26)]):
            with self.subTest(length=len(calls)):
                response = self.client.post("/v3/batch/", {"requests": calls}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Content-Type"], "application/problem+json")
