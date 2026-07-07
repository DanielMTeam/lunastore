import logging

from django.test import TestCase
from django.urls import reverse

from apps.marketplace.models import Application, Category
from apps.user.models import User

logger = logging.getLogger("marketplace")


class CategoryModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info("[Marketplace APP; Category MODEL] Creating test data in DB...")
        cls.category = Category.objects.create(
            name="TestCategory", description="TestCategory description", icon="top"
        )

    def test_category_name_content(self):
        logger.info('[Marketplace APP; Category MODEL] Testing "name" field...')
        obj = Category.objects.get(id=self.category.id)
        self.assertEqual(obj.name, "TestCategory")

    def test_str_method(self):
        self.assertEqual(str(self.category), "TestCategory")


class ApplicationModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info("[Marketplace APP; Application MODEL] Creating test data in DB...")
        # create user, because that's important for 'Application' object
        cls.user = User.objects.create(username="DevUser", password="password123")
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
        logger.info('[Marketplace APP; Application MODEL] Testing "title" field...')
        obj = Application.objects.get(id=self.application.id)
        self.assertEqual(obj.title, "TestApplication")

    def test_str_method(self):
        self.assertEqual(str(self.application), "TestApplication")


class HomePageTest(TestCase):
    def test_url_by_url(self):
        logger.info("[Marketplace APP; Home PAGE] Testing URL by direct path...")
        resp = self.client.get("/index.php")
        self.assertEqual(resp.status_code, 200)

    def test_url_by_name(self):
        logger.info("[Marketplace APP; Home PAGE] Testing URL by name...")
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)

from constance.test import override_config
from apps.marketplace.models import Distribution

class ProxyDownloadTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="TestProxyUser", password="password123")
        cls.application = Application.objects.create(
            user=cls.user,
            title="Test App Name",
            description="Proxy testing",
        )
        cls.distribution = Distribution.objects.create(
            app=cls.application,
            version="1.0.4",
            url="https://cloud.example.com/v1/files/download?id=123&token=abc#file.zip",
            changelog="Test proxy"
        )

    @override_config(ENABLE_DISTRIBUTION_PROXY=True)
    def test_proxy_headers(self):
        # check proxy headers and filename logic
        url = reverse("download_action", kwargs={"dist_pk": self.distribution.pk})
        resp = self.client.get(f"{url}?proxy=1")
        
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["X-Accel-Redirect"], "/proxy_external_url/")
        self.assertEqual(resp["X-Target-Url"], self.distribution.url)
        self.assertIn('filename="Test_App_Name_1.0.4.zip"', resp["Content-Disposition"])
