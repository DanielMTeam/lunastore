import logging
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.marketplace.models import (
    Application,
    Category,
    Collection,
    CollectionItem,
    Distribution,
)

logger = logging.getLogger("core")
User = get_user_model()


class SitemapAndRobotsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        logger.info("[Core APP; Sitemap TEST] Setting up test data...")
        cls.author = User.objects.create_user(
            username="author_user",
            password="testpassword123",
            email="author@example.com",
            is_active=True,
        )
        cls.inactive_user = User.objects.create_user(
            username="inactive_user",
            password="testpassword123",
            email="inactive@example.com",
            is_active=False,
        )

        cls.public_category = Category.objects.create(
            name="PublicCategory",
            description="Public category description",
            is_admin_only=False,
        )
        cls.admin_category = Category.objects.create(
            name="AdminCategory",
            description="Admin category description",
            is_admin_only=True,
        )

        cls.public_app = Application.objects.create(
            user=cls.author,
            title="PublicApp",
            description="Public app description",
            is_private=False,
            is_under_dmca=False,
        )
        cls.public_app.categories.add(cls.public_category)

        cls.dmca_app = Application.objects.create(
            user=cls.author,
            title="DmcaApp",
            description="Dmca app description",
            is_private=False,
            is_under_dmca=True,
        )

        cls.distribution = Distribution.objects.create(
            app=cls.public_app,
            version="1.0.0",
            url="https://example.com/dist.zip",
            changelog="Initial release",
        )

        cls.dmca_distribution = Distribution.objects.create(
            app=cls.dmca_app,
            version="1.0.0",
            url="https://example.com/dmca.zip",
            changelog="DMCA release",
        )

        cls.private_app = Application.objects.create(
            user=cls.author,
            title="PrivateApp",
            description="Private app description",
            is_private=True,
        )

        cls.deleted_app = Application.objects.create(
            user=cls.author,
            title="DeletedApp",
            description="Deleted app description",
            is_private=False,
        )
        cls.deleted_app.delete()

        cls.public_collection = Collection.objects.create(
            owner=cls.author,
            title="PublicCollection",
            description="Public collection description",
            is_public=True,
            is_system=False,
        )
        CollectionItem.objects.create(
            collection=cls.public_collection,
            application=cls.public_app,
        )

        cls.empty_collection = Collection.objects.create(
            owner=cls.author,
            title="EmptyCollection",
            description="Empty collection",
            is_public=True,
            is_system=False,
        )

        cls.private_collection = Collection.objects.create(
            owner=cls.author,
            title="PrivateCollection",
            description="Private collection description",
            is_public=False,
            is_system=False,
        )
        cls.system_collection = Collection.objects.create(
            owner=cls.author,
            title="Likes",
            description="System likes",
            is_public=True,
            is_system=True,
        )

    def test_sitemap_xml_response(self):
        logger.info("[Core APP; Sitemap TEST] Testing /sitemap.xml...")
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.headers["Content-Type"])

        content = response.content.decode("utf-8")
        # Check public items
        self.assertIn("/index.php", content)
        self.assertIn(f"/category.php?id={self.public_category.id}", content)
        self.assertIn(f"/app.php?id={self.public_app.id}", content)
        self.assertIn(f"/download.php?id={self.public_app.id}", content)
        self.assertIn(f"/collections.php?page=view&amp;id={self.public_collection.id}", content)
        self.assertIn(f"/profile.php?id={self.author.id}", content)
        self.assertIn("/help_center.php?page=faq", content)

        # Check that private/admin/dmca/empty items are excluded
        self.assertNotIn(f"/app.php?id={self.dmca_app.id}", content)
        self.assertNotIn(f"/download.php?id={self.dmca_app.id}", content)
        self.assertNotIn(f"/category.php?id={self.admin_category.id}", content)
        self.assertNotIn(f"/app.php?id={self.private_app.id}", content)
        self.assertNotIn(f"/app.php?id={self.deleted_app.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.empty_collection.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.private_collection.id}", content)
        self.assertNotIn(f"/collections.php?page=view&amp;id={self.system_collection.id}", content)
        self.assertNotIn(f"/profile.php?id={self.inactive_user.id}", content)
        self.assertNotIn("/admin/", content)
        self.assertNotIn("/login.php", content)

    def test_sitemap_sections(self):
        logger.info("[Core APP; Sitemap TEST] Testing /sitemap-<section>.xml...")
        for section in ["static", "categories", "apps", "downloads", "collections", "authors"]:
            response = self.client.get(f"/sitemap-{section}.xml")
            self.assertEqual(response.status_code, 200)
            self.assertIn("application/xml", response.headers["Content-Type"])

    def test_robots_txt_response(self):
        logger.info("[Core APP; Sitemap TEST] Testing /robots.txt...")
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["Content-Type"])
        self.assertEqual(response.headers.get("Cache-Control"), "public, max-age=86400")

        content = response.content.decode("utf-8")
        self.assertIn("User-agent: *", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /method/", content)
        self.assertIn("Disallow: /login.php", content)
        self.assertIn("Disallow: /register.php", content)
        self.assertIn("Disallow: /settings.php", content)
        self.assertIn("Disallow: /app_add.php", content)
        self.assertIn("Sitemap: https://testserver/sitemap.xml", content)
