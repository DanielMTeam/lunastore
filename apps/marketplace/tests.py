from constance.test import override_config
from apps.marketplace.models import Distribution
import logging
from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.logger.services import AUTO_APPROVAL_MARKER
from apps.marketplace.models import (
    AppCreateRequests,
    AppEditRequests,
    Application,
    Category,
    Collection,
    CollectionFavorite,
    CollectionItem,
    DistributionCreateRequests,
    DistributionEditRequests,
    Review,
    get_or_create_likes_collection,
)
from apps.marketplace.services.moderation import (
    approve_app_create_request,
    auto_approve_request,
)
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


@override_settings(RATELIMIT_BACKEND='memory', RATELIMIT_ENABLE=False)
class ViewModeSloganTest(TestCase):
    @classmethod
    @patch("apps.core.search.service.SearchService.index_application")
    @patch("apps.core.search.service.SearchService.index_user")
    def setUpTestData(cls, mock_index_user, mock_index_app):
        cls.user = User.objects.create_user(
            username="SloganUser", password="password123", email="slogan@example.com"
        )
        cls.category = Category.objects.create(
            name="Tools",
            description="Tools category",
        )
        cls.slogan_65 = "A freeware task manager and system monitor for Microsoft Windows."
        cls.app = Application.objects.create(
            user=cls.user,
            title="Process Explorer",
            description="Process Explorer desc",
            slogan=cls.slogan_65,
            price=0,
            is_private=False,
            is_under_dmca=False,
        )
        cls.app.categories.add(cls.category)

    def test_category_view_slogan_tiles(self):
        resp = self.client.get(f"/category.php?id={self.category.id}&view=tiles")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A freeware task manager and system monitor f…")

    def test_category_view_slogan_list(self):
        resp = self.client.get(f"/category.php?id={self.category.id}&view=list")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.slogan_65)
        self.assertNotContains(resp, "A freeware task manager and system monitor f…")

    def test_search_view_slogan_tiles(self):
        resp = self.client.get("/search.php?view=tiles")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A freeware task manager and system monitor f…")

    def test_search_view_slogan_list(self):
        resp = self.client.get("/search.php?view=list")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.slogan_65)
        self.assertNotContains(resp, "A freeware task manager and system monitor f…")

    def test_store_listing_slogan_tiles(self):
        resp = self.client.get("/store.php?show=new&view=tiles")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A freeware task manager and system monitor f…")

    def test_store_listing_slogan_list(self):
        resp = self.client.get("/store.php?show=new&view=list")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.slogan_65)
        self.assertNotContains(resp, "A freeware task manager and system monitor f…")

    @patch("apps.core.search.service.SearchService.index_application")
    def test_long_slogan_in_list_view_truncated_at_85(self, _mock_idx):
        long_slogan = "A" * 120
        self.app.slogan = long_slogan
        self.app.save(update_fields=["slogan"])
        try:
            resp = self.client.get(f"/category.php?id={self.category.id}&view=list")
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "A" * 84 + "…")
            self.assertNotContains(resp, long_slogan + "</p>")
        finally:
            self.app.slogan = self.slogan_65
            self.app.save(update_fields=["slogan"])


class TrustedAuthorAutoApprovalTest(TestCase):
    """Requests from authors flagged as trusted are approved on the spot.

    The automatic approval must keep the regular audit trail: an admin
    LogEntry (mirrored to Telegram), an explicit Telegram message, and the
    usual in-app notification for the author.
    """

    @classmethod
    def setUpTestData(cls):
        logger.info(
            "[Marketplace APP; TrustedAuthor MODEL] Creating test data in DB...")
        cls.trusted = User.objects.create(
            username="TrustedDev",
            password="password123",
            email="trusted@example.com",
            is_trusted=True)
        cls.regular = User.objects.create(
            username="RegularDev",
            password="password123",
            email="regular@example.com")
        cls.moderator = User.objects.create(
            username="Moderator",
            password="password123",
            email="moderator@example.com",
            is_staff=True)
        cls.app = Application.objects.create(
            user=cls.regular,
            title="ExistingApp",
            description="TestDescription",
            slogan="TestSlogan",
            price=0,
        )

    def _app_create_request(self, user):
        return AppCreateRequests.objects.create(
            user=user,
            title="AutoApp",
            description="TestDescription",
            slogan="TestSlogan",
            price=0,
        )

    def _app_edit_request(self, user):
        return AppEditRequests.objects.create(
            user=user,
            target_application=self.app,
            title="RenamedApp",
            description="TestDescription",
            slogan="TestSlogan",
            price=0,
        )

    def _dist_create_request(self, user):
        return DistributionCreateRequests.objects.create(
            user=user,
            app=self.app,
            version="1.0",
            changelog="Initial",
            virustotal_url="https://www.virustotal.com/gui/example",
        )

    def _dist_edit_request(self, user):
        distribution = Distribution.objects.create(
            app=self.app, version="1.0", changelog="Initial")
        return DistributionEditRequests.objects.create(
            user=user,
            target_distribution=distribution,
            app=self.app,
            version="2.0",
            changelog="Updated",
        )

    def _approval_log(self, request_model, pk):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(request_model),
            object_id=str(pk),
        ).first()

    def _notification_titles(self, mock_send_notification):
        calls = mock_send_notification.enqueue.call_args_list
        return [call[1].get("title_key") for call in calls]

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_regular_author_keeps_request_pending(self, mock_send_notification):
        req = self._app_create_request(self.regular)

        self.assertIsNone(auto_approve_request(req))

        req.refresh_from_db()
        self.assertEqual(req.status, "pending")
        self.assertFalse(Application.objects.filter(title="AutoApp").exists())
        self.assertFalse(mock_send_notification.enqueue.called)

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_trusted_author_app_request_is_approved(
            self, mock_send_notification):
        req = self._app_create_request(self.trusted)

        created = auto_approve_request(req)

        self.assertIsInstance(created, Application)
        self.assertEqual(created.title, "AutoApp")
        self.assertEqual(created.user, self.trusted)
        self.assertFalse(AppCreateRequests.objects.filter(pk=req.pk).exists())
        self.assertIn(
            "NOTIF_APPREQ_ACCEPTED_TITLE",
            self._notification_titles(mock_send_notification))

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_trusted_author_app_edit_request_is_applied(
            self, mock_send_notification):
        req = self._app_edit_request(self.trusted)

        updated = auto_approve_request(req)

        self.assertIsInstance(updated, Application)
        self.app.refresh_from_db()
        self.assertEqual(self.app.title, "RenamedApp")
        self.assertFalse(AppEditRequests.objects.filter(pk=req.pk).exists())
        self.assertIn(
            "NOTIF_APPEDITREQ_ACCEPTED_TITLE",
            self._notification_titles(mock_send_notification))

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_trusted_author_dist_create_request_is_published(
            self, mock_send_notification):
        req = self._dist_create_request(self.trusted)

        created = auto_approve_request(req)

        self.assertIsInstance(created, Distribution)
        self.assertEqual(created.version, "1.0")
        self.assertEqual(created.app, self.app)
        self.assertFalse(
            DistributionCreateRequests.objects.filter(pk=req.pk).exists())
        self.assertIn(
            "NOTIF_DISTREQ_ACCEPTED_TITLE",
            self._notification_titles(mock_send_notification))

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_trusted_author_dist_edit_request_is_applied(
            self, mock_send_notification):
        req = self._dist_edit_request(self.trusted)

        created = auto_approve_request(req)

        self.assertIsInstance(created, Distribution)
        self.assertEqual(created.version, "2.0")
        self.assertFalse(
            DistributionEditRequests.objects.filter(pk=req.pk).exists())
        self.assertIn(
            "NOTIF_DISTEDITREQ_ACCEPTED_TITLE",
            self._notification_titles(mock_send_notification))

    @override_settings(TELEGRAM_LOGGER_ENABLED=True)
    @patch("apps.marketplace.services.moderation.send_telegram_notification")
    @patch("apps.core.signals.send_telegram_notification")
    @patch("apps.marketplace.services.moderation.send_notification")
    def test_auto_approval_is_logged_and_sent_to_telegram(
            self, mock_send_notification, mock_log_tg, mock_auto_tg):
        req = self._app_create_request(self.trusted)

        auto_approve_request(req)

        log_entry = self._approval_log(AppCreateRequests, req.pk)
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.action_flag, CHANGE)
        self.assertEqual(log_entry.user_id, self.trusted.pk)
        self.assertIn("status approved", log_entry.change_message)
        self.assertIn(AUTO_APPROVAL_MARKER, log_entry.change_message)

        # admin log -> moderator telegram chat
        self.assertEqual(mock_log_tg.call_count, 1)
        log_message = mock_log_tg.call_args[0][0]
        self.assertIn(AUTO_APPROVAL_MARKER, log_message)
        self.assertIn("⚡️", log_message)

        # dedicated telegram ping for the automatic approval
        self.assertEqual(mock_auto_tg.call_count, 1)
        auto_message = mock_auto_tg.call_args[0][0]
        self.assertIn("TrustedDev", auto_message)
        self.assertIn("AutoApp", auto_message)
        self.assertIn("одобрена автоматически", auto_message)

    @override_settings(TELEGRAM_LOGGER_ENABLED=True)
    @patch("apps.marketplace.services.moderation.send_telegram_notification")
    @patch("apps.core.signals.send_telegram_notification")
    @patch("apps.marketplace.services.moderation.send_notification")
    def test_manual_approval_is_logged_without_auto_marker(
            self, mock_send_notification, mock_log_tg, mock_auto_tg):
        req = self._app_create_request(self.regular)

        created = approve_app_create_request(req, actor=self.moderator)

        self.assertIsInstance(created, Application)
        log_entry = self._approval_log(AppCreateRequests, req.pk)
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user_id, self.moderator.pk)
        self.assertIn("status approved", log_entry.change_message)
        self.assertNotIn(AUTO_APPROVAL_MARKER, log_entry.change_message)

        # moderators keep the regular log, but no automatic ping is sent
        self.assertEqual(mock_log_tg.call_count, 1)
        self.assertIn("✅", mock_log_tg.call_args[0][0])
        self.assertFalse(mock_auto_tg.called)

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_already_approved_request_is_not_processed_twice(
            self, mock_send_notification):
        req = self._app_create_request(self.trusted)
        req.status = "approved"
        req.save()

        self.assertIsNone(auto_approve_request(req))
        self.assertEqual(mock_send_notification.enqueue.call_count, 0)

    @patch("apps.marketplace.services.moderation.send_notification")
    def test_failing_auto_approval_falls_back_to_manual_moderation(
            self, mock_send_notification):
        req = self._app_create_request(self.trusted)
        mock_send_notification.enqueue.side_effect = RuntimeError("boom")

        self.assertIsNone(auto_approve_request(req))
        self.assertTrue(AppCreateRequests.objects.filter(pk=req.pk).exists())


class RatingAndCollectionOptimizationTests(TestCase):
    @classmethod
    @patch("apps.core.search.service.SearchService.index_application")
    @patch("apps.core.search.service.SearchService.index_user")
    def setUpTestData(cls, mock_index_user, mock_index_app):
        cls.user1 = User.objects.create_user(username="rater1", password="password123", email="r1@example.com")
        cls.user2 = User.objects.create_user(username="rater2", password="password123", email="r2@example.com")
        cls.app = Application.objects.create(
            user=cls.user1,
            title="RatedApp",
            description="Rated app description",
            price=0,
        )

    def test_rating_cache_updates_on_review_save_and_delete(self):
        # Initial rating cache is 0
        self.assertEqual(self.app.rating_cache, 0.0)
        self.assertEqual(self.app.reviews_count, 0)
        self.assertEqual(self.app.avg_rating, 0.0)

        # Create review 1: rating 4
        r1 = Review.objects.create(application=self.app, user=self.user1, rating=4)
        self.app.refresh_from_db()
        self.assertEqual(self.app.rating_cache, 4.0)
        self.assertEqual(self.app.reviews_count, 1)
        self.assertEqual(self.app.avg_rating, 4.0)

        # Create review 2: rating 5 -> average is 4.5
        r2 = Review.objects.create(application=self.app, user=self.user2, rating=5)
        self.app.refresh_from_db()
        self.assertEqual(self.app.rating_cache, 4.5)
        self.assertEqual(self.app.reviews_count, 2)
        self.assertEqual(self.app.avg_rating, 4.5)

        # Delete review 2 -> average returns to 4.0
        r2.delete()
        self.app.refresh_from_db()
        self.assertEqual(self.app.rating_cache, 4.0)
        self.assertEqual(self.app.reviews_count, 1)
        self.assertEqual(self.app.avg_rating, 4.0)

        # Delete review 1 -> average returns to 0.0
        r1.delete()
        self.app.refresh_from_db()
        self.assertEqual(self.app.rating_cache, 0.0)
        self.assertEqual(self.app.reviews_count, 0)
        self.assertEqual(self.app.avg_rating, 0.0)

    def test_avg_rating_queries_count_is_zero(self):
        Review.objects.create(application=self.app, user=self.user1, rating=5)
        app = Application.objects.get(pk=self.app.pk)
        # avg_rating should read rating_cache directly without any SQL queries
        with self.assertNumQueries(0):
            val = app.avg_rating
            star = app.star_class
        self.assertEqual(val, 5.0)
        self.assertEqual(star, "r5")

    def test_collection_mosaic_icons_uses_prefetched_items(self):
        col = Collection.objects.create(owner=self.user1, title="TestCol")
        CollectionItem.objects.create(collection=col, application=self.app)

        from django.db.models import Prefetch
        prefetched_col = Collection.objects.prefetch_related(
            Prefetch("items", queryset=CollectionItem.objects.select_related("application"))
        ).get(pk=col.pk)

        # With prefetched items, mosaic_icons(4) should execute 0 queries
        with self.assertNumQueries(0):
            icons = prefetched_col.mosaic_icons(4)
        self.assertEqual(len(icons), 4)

    def test_collection_serializer_uses_annotated_items_count(self):
        from apps.marketplace.serializers import CollectionSerializer
        from django.db.models import Count

        col = Collection.objects.create(owner=self.user1, title="TestSerializerCol")
        CollectionItem.objects.create(collection=col, application=self.app)

        annotated_col = Collection.objects.annotate(items_count=Count("items")).get(pk=col.pk)
        serializer = CollectionSerializer(annotated_col)
        # Serializer should use the annotated items_count directly
        self.assertEqual(serializer.data["items_count"], 1)
