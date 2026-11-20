import json
from unittest.mock import patch

from constance.test import override_config
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.forms.utils import ErrorDict

from apps.marketplace.forms import AppCreateForm, AppScreenshotForm


@override_config(SCREENSHOT_COUNT=5)
class ScreenshotLimitTests(SimpleTestCase):
    def test_upload_accepts_five_and_rejects_six(self):
        form = AppCreateForm(data={})
        form._errors = ErrorDict()
        with patch.object(form, "validate_cdn_token", side_effect=lambda token, **kwargs: {"file_id": token}), patch.object(
            form, "get_cdn_file_info", side_effect=lambda file_id, fields: {"path": file_id}
        ):
            form.cleaned_data = {"cdn_screenshots_tokens": json.dumps([str(i) for i in range(5)])}
            self.assertEqual(len(form.clean()["cdn_screenshots_data"]), 5)
            form.cleaned_data = {"cdn_screenshots_tokens": json.dumps([str(i) for i in range(6)])}
            with self.assertRaises(ValidationError):
                form.clean()

    def test_screenshot_form_follows_configured_limit(self):
        form = AppScreenshotForm()
        self.assertIn("screenshot_5", form.fields)
        self.assertNotIn("screenshot_6", form.fields)
        self.assertEqual(AppCreateForm(data={}).screenshot_limit, 5)
