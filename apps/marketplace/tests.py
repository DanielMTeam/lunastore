from constance.test import override_config
from apps.marketplace.models import Distribution
import logging

from django.test import TestCase
from django.urls import reverse

from apps.marketplace.models import Application, Category, Collection, CollectionFavorite, CollectionItem, get_or_create_likes_collection
from apps.user.models import User

logger = logging.getLogger("marketplace")


class CategoryModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info(
            "[Marketplace APP; Category MODEL] Creating test data in DB...")
        cls.category = Category.objects.create(
            name="TestCategory",
            description="TestCategory description",
            icon="top")

    def test_category_name_content(self):
        logger.info(
            '[Marketplace APP; Category MODEL] Testing "name" field...')
        obj = Category.objects.get(id=self.category.id)
        self.assertEqual(obj.name, "TestCategory")

    def test_str_method(self):
        self.assertEqual(str(self.category), "TestCategory")


class ApplicationModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info(
            "[Marketplace APP; Application MODEL] Creating test data in DB...")
        # create user, because that's important for 'Application' object
        cls.user = User.objects.create(
            username="DevUser", password="password123")
        cls.category = Category.objects.create(name="Apps", description="Desc")

        cls.application = Application.objects.create(
            user=cls.user,
            title="TestApplication",
            description="TestDescription",
            slogan="TestSlogan",
            price=0,
            developer_site="https://fayzetw.in",
        )
        cls.application.categories.add(cls.category)

    def test_application_name_content(self):
        logger.info(
            '[Marketplace APP; Application MODEL] Testing "title" field...')
        obj = Application.objects.get(id=self.application.id)
        self.assertEqual(obj.title, "TestApplication")

    def test_str_method(self):
        self.assertEqual(str(self.application), "TestApplication")


class HomePageTest(TestCase):
    def test_url_by_url(self):
        logger.info(
            "[Marketplace APP; Home PAGE] Testing URL by direct path...")
        resp = self.client.get("/index.php")
        self.assertEqual(resp.status_code, 200)

    def test_url_by_name(self):
        logger.info("[Marketplace APP; Home PAGE] Testing URL by name...")
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)


class ProxyDownloadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username="TestProxyUser",
            password="password123")
        cls.application = Application.objects.create(
            user=cls.user,
            title="Test App Name",
            description="Proxy testing",
        )
        cls.distribution = Distribution.objects.create(
            app=cls.application,
            version="1.0.4",
            url="https://cloud.example.com/v1/files/download?id=123&token=abc#file.zip",
            changelog="Test proxy")

    @override_config(ENABLE_DISTRIBUTION_PROXY=True)
    def test_proxy_headers(self):
        # check proxy headers and filename logic
        url = reverse(
            "download_action", kwargs={
                "dist_pk": self.distribution.pk})
        resp = self.client.get(f"{url}?proxy=1")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["X-Accel-Redirect"],
                         f"/_px/{self.distribution.url}")
        self.assertIn(
            'filename="Test_App_Name_1.0.4.zip"',
            resp["Content-Disposition"])


class CollectionModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info("[Marketplace APP; Collection MODEL] Creating test data...")
        cls.user = User.objects.create(username="ColUser", password="password123", email="coluser@example.com")
        cls.other = User.objects.create(username="ColOther", password="password123", email="colother@example.com")
        cls.app = Application.objects.create(
            user=cls.user,
            title="ColApp",
            description="Desc",
            slogan="Slogan",
            price=0,
        )
        cls.collection = Collection.objects.create(
            owner=cls.user,
            title="My Collection",
            description="Desc",
            is_public=True,
        )
        CollectionItem.objects.create(collection=cls.collection, application=cls.app)

    def test_collection_title(self):
        obj = Collection.objects.get(id=self.collection.id)
        self.assertEqual(obj.title, "My Collection")

    def test_unique_item(self):
        with self.assertRaises(Exception):
            CollectionItem.objects.create(
                collection=self.collection, application=self.app
            )

    def test_likes_collection_once(self):
        a = get_or_create_likes_collection(self.user)
        b = get_or_create_likes_collection(self.user)
        self.assertEqual(a.id, b.id)
        self.assertTrue(a.is_system)

    def test_mosaic_icons(self):
        icons = self.collection.mosaic_icons(4)
        self.assertEqual(len(icons), 4)

    def test_soft_delete(self):
        self.collection.delete()
        self.assertFalse(
            Collection.objects.filter(id=self.collection.id).exists()
        )


class CollectionPageTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ColPageUser", password="password123", email="colpage@example.com"
        )
        cls.other = User.objects.create_user(
            username="ColPageOther", password="password123", email="colpageother@example.com"
        )
        cls.app = Application.objects.create(
            user=cls.user,
            title="PageApp",
            description="Desc",
            slogan="Slogan",
            price=0,
        )
        cls.public_col = Collection.objects.create(
            owner=cls.user,
            title="Public Col",
            description="Public",
            is_public=True,
        )
        cls.private_col = Collection.objects.create(
            owner=cls.user,
            title="Private Col",
            description="Private",
            is_public=False,
        )

    def test_guest_list_redirects(self):
        resp = self.client.get("/collections.php")
        self.assertEqual(resp.status_code, 302)

    def test_list_ok(self):
        self.client.login(username="ColPageUser", password="password123")
        resp = self.client.get("/collections.php")
        self.assertEqual(resp.status_code, 200)

    def test_view_public(self):
        resp = self.client.get(
            f"/collections.php?page=view&id={self.public_col.id}"
        )
        self.assertEqual(resp.status_code, 200)

    def test_view_private_forbidden(self):
        self.client.login(username="ColPageOther", password="password123")
        resp = self.client.get(
            f"/collections.php?page=view&id={self.private_col.id}"
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/collections.php")

    def test_create_collection(self):
        self.client.login(username="ColPageUser", password="password123")
        resp = self.client.post(
            "/collections.php?page=create",
            {
                "title_ru": "New Col",
                "description_ru": "New desc",
                "is_public": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Collection.objects.filter(owner=self.user, title="New Col").exists()
            or Collection.objects.filter(owner=self.user, title_ru="New Col").exists()
        )

    def test_add_app(self):
        self.client.login(username="ColPageUser", password="password123")
        resp = self.client.post(
            f"/collections.php?act=add&appid={self.app.id}",
            {"collection_ids": self.public_col.id, "appid": self.app.id},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            CollectionItem.objects.filter(
                collection=self.public_col, application=self.app
            ).exists()
        )

    def test_favorite_toggle(self):
        self.client.login(username="ColPageOther", password="password123")
        resp = self.client.get(
            f"/collections.php?act=favorite&id={self.public_col.id}"
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            CollectionFavorite.objects.filter(
                user=self.other, collection=self.public_col
            ).exists()
        )

    def test_delete_collection(self):
        self.client.login(username="ColPageUser", password="password123")
        col = Collection.objects.create(
            owner=self.user, title="ToDelete", is_public=True
        )
        resp = self.client.post(f"/collections.php?page=delete&id={col.id}")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Collection.objects.filter(id=col.id).exists())

