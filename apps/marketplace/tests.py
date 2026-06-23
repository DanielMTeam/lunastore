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
        # Создаем юзера, так как он обязателен для Application
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
