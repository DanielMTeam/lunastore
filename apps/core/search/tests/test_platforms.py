from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.core.search.documents import application_to_document
from apps.core.search.service import SearchService
from apps.marketplace.forms import AppCreateForm, DistributionCreateForm
from apps.marketplace.models import Application, AppEditRequests, Category, Distribution, Platform
from apps.marketplace.services.moderation import approve_app_edit_request
from apps.marketplace.serializers import ApplicationSerializer as V1ApplicationSerializer
from apps.api.v2.views import ApplicationSerializer as V2ApplicationSerializer


@override_settings(MEILISEARCH_ENABLED=False)
class PlatformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.xp, _ = Platform.objects.get_or_create(code="windows_xp", defaults={"name": "Windows XP"})
        cls.win7, _ = Platform.objects.get_or_create(code="windows_7", defaults={"name": "Windows 7"})
        cls.user = get_user_model().objects.create_user(username="platform_dev", password="password")
        cls.category = Category.objects.create(name="Tools", description="Tools")
        cls.app = Application.objects.create(user=cls.user, title="Platform Tool", description="Tool")
        cls.app.categories.add(cls.category)
        cls.app.platforms.add(cls.xp)

    def test_form_defaults_and_distribution_choices(self):
        self.assertIn(self.xp.pk, AppCreateForm().initial["platforms"])
        form = DistributionCreateForm(user=self.user, app=self.app)
        self.assertEqual(list(form.fields["platform"].queryset), [self.xp])

    def test_vista_is_available_for_application_and_distribution(self):
        vista = Platform.objects.get(code="windows_vista")
        self.assertEqual(vista.name, "Windows Vista")
        self.assertIn(vista, AppCreateForm(data={}).fields["platforms"].queryset)
        self.app.platforms.add(vista)
        field = DistributionCreateForm(user=self.user, app=self.app).fields["platform"]
        self.assertIn(vista, field.queryset)
        self.assertEqual(field.widget.attrs["size"], 4)
        self.assertFalse(field.widget.allow_multiple_selected)

    def test_search_fallback_filters_before_pagination(self):
        ids, count = SearchService.search_application_ids("Platform", platform_id=self.xp.pk)
        self.assertEqual((ids, count), ([self.app.pk], 1))
        ids, count = SearchService.search_application_ids("Platform", platform_id=self.win7.pk)
        self.assertEqual((ids, count), ([], 0))
        self.assertIn(self.xp.pk, application_to_document(self.app)["platform_ids"])

    def test_api_contracts_and_category_filter(self):
        self.assertNotIn("platforms", V1ApplicationSerializer(self.app).data)
        self.assertEqual(V2ApplicationSerializer(self.app).data["platforms"][0]["code"], "windows_xp")
        with override_settings(ROOT_URLCONF="lunastore.urls_api"):
            response = self.client.get(f"/v2/category/{self.category.pk}/apps/", {"platform": "windows_7"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_distribution_rejects_unsupported_platform(self):
        dist = Distribution(app=self.app, platform=self.win7, version="1", changelog="test")
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            dist.clean()

    def test_moderation_rejects_removal_of_used_platform(self):
        Distribution.objects.create(app=self.app, platform=self.xp, version="1", changelog="test")
        request = AppEditRequests.objects.create(
            user=self.user, target_application=self.app, title="Platform Tool", description="Tool")
        request.platforms.add(self.win7)
        self.assertIsNone(approve_app_edit_request(request, actor=self.user))
        self.assertTrue(self.app.platforms.filter(pk=self.xp.pk).exists())

    def test_web_category_filter(self):
        response = self.client.get("/category.php", {"id": self.category.pk, "platform": "windows_7"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Platform Tool")
        response = self.client.get("/category.php", {"id": self.category.pk, "platform": "windows_xp"})
        self.assertContains(response, "Platform Tool")
