from constance.test import override_config
from apps.marketplace.models import Distribution
import logging
from unittest.mock import patch

from django.test import TestCase, override_settings
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
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="HomeUser",
            password="password123",
            email="homeuser@example.com",
        )
        cls.category = Category.objects.create(
            name="HomeCat",
            description="Home category desc",
            icon="themes",
        )
        cls.app = Application.objects.create(
            user=cls.user,
            title="HomeApp",
            description="Home description long enough",
            slogan="Home slogan",
            price=0,
        )
        cls.app.categories.add(cls.category)

    def test_url_by_url(self):
        logger.info(
            "[Marketplace APP; Home PAGE] Testing URL by direct path...")
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get("/index.php")
        self.assertEqual(resp.status_code, 200)

    def test_url_by_name(self):
        logger.info("[Marketplace APP; Home PAGE] Testing URL by name...")
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)

    def test_rich_home_default(self):
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "index_rich.html")
        self.assertContains(resp, "HomeApp")

    def test_compact_home_via_cookie(self):
        self.client.cookies["home_layout"] = "compact"
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "index.html")

    def test_user_home_layout_overrides_cookie(self):
        self.user.home_layout = "compact"
        self.user.save(update_fields=["home_layout"])
        self.client.force_login(self.user)
        self.client.cookies["home_layout"] = "rich"
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(reverse("index"))
        self.assertTemplateUsed(resp, "index.html")

    @override_config(
        ANALYTICS_ENABLED=False,
        HOME_EDITOR_CHOICE_CATEGORY_ID=0,
        HOME_APP_OF_THE_DAY_ID=0,
    )
    def test_editor_choice_hidden_when_zero(self):
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.context["editor_choice"], None)

    @override_config(
        ANALYTICS_ENABLED=False,
        HOME_EDITOR_CHOICE_CATEGORY_ID=999999,
        HOME_APP_OF_THE_DAY_ID=0,
    )
    def test_editor_choice_missing_category(self):
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.context["editor_choice"], None)

    def test_home_category_block(self):
        from apps.marketplace.models import HomeCategoryBlock

        HomeCategoryBlock.objects.create(
            category=self.category,
            sort_order=1,
            is_enabled=True,
            apps_limit=4,
        )
        with override_config(
            ANALYTICS_ENABLED=False,
            HOME_EDITOR_CHOICE_CATEGORY_ID=0,
            HOME_APP_OF_THE_DAY_ID=0,
        ):
            resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.context["category_blocks"]) >= 1)
        self.assertContains(resp, "HomeCat")

    def test_store_listing_top(self):
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(reverse("store_listing") + "?show=top")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "store_listing.html")

    def test_store_listing_rejects_xss_show(self):
        with override_config(ANALYTICS_ENABLED=False):
            resp = self.client.get(
                reverse("store_listing")
                + "?show=top'-alert(1)-'"
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["show"], "top")
        self.assertNotContains(resp, "alert(1)")

    def test_soft_deleted_category_block_hidden(self):
        from apps.marketplace.models import HomeCategoryBlock

        deleted_cat = Category.objects.create(name="GoneCat", description="x")
        HomeCategoryBlock.objects.create(
            category=deleted_cat,
            sort_order=0,
            is_enabled=True,
            apps_limit=4,
        )
        deleted_cat.delete()
        with override_config(
            ANALYTICS_ENABLED=False,
            HOME_EDITOR_CHOICE_CATEGORY_ID=0,
            HOME_APP_OF_THE_DAY_ID=0,
        ):
            resp = self.client.get(reverse("index"))
        names = [b["category"].name for b in resp.context["category_blocks"]]
        self.assertNotIn("GoneCat", names)


class HomeLayoutSettingsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="UiUser",
            password="password123",
            email="uiuser@example.com",
        )

    def test_settings_ui_requires_login(self):
        resp = self.client.get(reverse("settings_ui"))
        self.assertEqual(resp.status_code, 302)

    def test_settings_ui_post_saves_layout(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("settings_ui"),
            {"home_view": "compact"},
        )
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.home_layout, "compact")
        self.assertEqual(resp.cookies["home_layout"].value, "compact")

    def test_settings_ui_rejects_invalid(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("settings_ui"),
            {"home_view": "weird"},
        )
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.home_layout, "rich")


class HomeServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="SvcUser",
            password="password123",
            email="svcuser@example.com",
        )
        cls.category = Category.objects.create(name="SvcCat", description="d")
        cls.app = Application.objects.create(
            user=cls.user,
            title="SvcApp",
            description="desc",
            slogan="slogan",
        )
        cls.app.categories.add(cls.category)

    @override_config(HOME_APP_OF_THE_DAY_ID=0, ANALYTICS_ENABLED=False)
    def test_app_of_the_day_fallback(self):
        from apps.marketplace.services.home import get_app_of_the_day

        with patch(
            "apps.analytics.services.get_app_of_the_day_id",
            return_value=None,
        ):
            app = get_app_of_the_day()
        self.assertIsNotNone(app)
        self.assertEqual(app.pk, self.app.pk)

    @override_config(HOME_APP_OF_THE_DAY_ID=0, ANALYTICS_ENABLED=False)
    def test_app_of_the_day_from_analytics(self):
        from apps.marketplace.services.home import get_app_of_the_day

        with patch(
            "apps.analytics.services.get_app_of_the_day_id",
            return_value=self.app.pk,
        ):
            app = get_app_of_the_day()
        self.assertEqual(app.pk, self.app.pk)

    def test_for_you_empty_without_analytics(self):
        from apps.marketplace.services.home import get_for_you_apps

        with patch(
            "apps.analytics.services.get_similar_app_ids",
            return_value=[],
        ):
            apps = get_for_you_apps(self.user.pk)
        self.assertEqual(apps, [])

    @override_config(HOME_EDITOR_CHOICE_CATEGORY_ID=0, ANALYTICS_ENABLED=False)
    def test_editor_choice_disabled(self):
        from apps.marketplace.services.home import get_editor_choice_block

        self.assertIsNone(get_editor_choice_block())

    def test_apps_for_category_filters_popular_by_membership(self):
        from apps.marketplace.services.home import get_apps_for_category

        other = Category.objects.create(name="OtherCat", description="o")
        other_app = Application.objects.create(
            user=self.user,
            title="OtherApp",
            description="desc",
            slogan="slogan",
        )
        other_app.categories.add(other)

        with patch(
            "apps.analytics.services.get_popular_apps",
            return_value=[
                {"app_id": other_app.pk, "count": 99},
                {"app_id": self.app.pk, "count": 10},
            ],
        ):
            apps = get_apps_for_category(self.category, limit=4)
        self.assertEqual([a.pk for a in apps], [self.app.pk])


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

    def test_collection_stats_view(self):
        self.client.login(username="ColPageUser", password="password123")
        resp = self.client.get(f"/collections.php?page=stats&id={self.public_col.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "collections_stats.html")


@override_settings(RATELIMIT_BACKEND='memory', RATELIMIT_ENABLE=False)
class AppStatsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="StatsOwner", password="password123", email="statsowner@example.com"
        )
        cls.other_user = User.objects.create_user(
            username="StatsOther", password="password123", email="statsother@example.com"
        )
        cls.app = Application.objects.create(
            user=cls.owner,
            title="StatsApp",
            description="App for stats",
            slogan="Slogan stats",
            price=0,
        )

    def test_app_stats_guest_redirects(self):
        resp = self.client.get(f"/app_stats.php/{self.app.pk}/")
        self.assertEqual(resp.status_code, 302)

    def test_app_stats_non_owner_forbidden(self):
        self.client.login(username="StatsOther", password="password123")
        resp = self.client.get(f"/app_stats.php/{self.app.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_app_stats_owner_ok(self):
        self.client.login(username="StatsOwner", password="password123")
        resp = self.client.get(f"/app_stats.php/{self.app.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "admin_app_stats.html")
        self.assertTemplateUsed(resp, "includes/xp_chart.html")
        self.assertIn("stats", resp.context)
