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
