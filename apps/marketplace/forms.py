import json
import os
import uuid
from urllib.parse import urlparse

import jwt
from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from modeltranslation.forms import TranslationModelForm
from . import translation
from .models import (
    AppCreateRequests,
    AppEditRequests,
    Application,
    AppReportRequests,
    Distribution,
    DistributionCreateRequests,
    DistributionEditRequests,
)
from apps.core.mixins import CDNTokenValidationMixin

_TRANS_FIELDS = ["title", "slogan", "description", "requirements", "changelog"]

def get_translated_fields_list(base_fields):
    expanded = []
    for field in base_fields:
        if field in _TRANS_FIELDS:
            for lang_code, _ in settings.LANGUAGES:
                expanded.append(f"{field}_{lang_code}")
        else:
            expanded.append(field)
    return expanded

def get_translated_widgets_dict(base_widgets_configs):
    widgets = {}
    for field, widget in base_widgets_configs.items():
        if field in _TRANS_FIELDS:
            for lang_code, _ in settings.LANGUAGES:
                widgets[f"{field}_{lang_code}"] = widget
        else:
            widgets[field] = widget
    return widgets

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def to_python(self, data):
        return data

    def clean(self, data, initial=None):
        if not data and not self.required:
            return None
        return data


class AppScreenshotForm(TranslationModelForm):
    class Meta:
        model = Application
        fields = [
            "title",
            "category",
            "description",
            "slogan",
            "developer_site",
            "is_demo",
            "is_under_dmca",
            "price",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input-text", "style": "width: 100%;"}
            ),
            "slogan": forms.Textarea(
                attrs={"class": "brief_intro", "rows": 3, "style": "resize: none;"}
            ),
            "description": forms.Textarea(
                attrs={"class": "brief_intro", "style": "height: 150px;"}
            ),
            "requirements": forms.Textarea(
                attrs={"class": "brief_intro", "style": "height: 150px;"}
            ),
            "original_author": forms.TextInput(
                attrs={"class": "input-text"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # check existing screenshots
        if self.instance and self.instance.pk:
            # get screenshots list
            screenshots = self.instance.screenshots or []

            for i in range(1, settings.SCREENSHOT_COUNT + 1):
                field_name = f"screenshot_{i}"
                clear_field_name = f"clear_screenshot_{i}"
                list_index = i - 1

                # check if screenshot exists
                if len(screenshots) > list_index and screenshots[list_index]:
                    path = screenshots[list_index]
                    url = f"/staticfiles/{path}"
                    self.fields[field_name].help_text = mark_safe(
                        f'<a href="{url}" target="_blank">'
                        f'<img src="{url}" style="max-width: 150px; max-height: 150px; border: 1px solid #ccc;"/>'
                        f"</a>"
                    )
                else:
                    # if no screenshot, hide clear checkbox
                    self.fields[clear_field_name].widget = forms.HiddenInput()
                    self.fields[clear_field_name].label = ""

    def save(self, commit=True):
        app_instance = super().save(commit=False)
        destination_dir = os.path.join(settings.MEDIA_ROOT, "ugc", "screenshots")
        os.makedirs(destination_dir, exist_ok=True)

        # put current screenshots in a list
        current_paths = (
            app_instance.screenshots
            if isinstance(app_instance.screenshots, list)
            else []
        )
        # we will build the final paths list here
        final_paths = (current_paths + [None] * settings.SCREENSHOT_COUNT)[
            : settings.SCREENSHOT_COUNT
        ]

        for i in range(1, settings.SCREENSHOT_COUNT + 1):
            clear_field_name = f"clear_screenshot_{i}"
            upload_field_name = f"screenshot_{i}"
            path_index = i - 1

            # get uploaded file
            uploaded_file = self.cleaned_data.get(upload_field_name)

            # if user wants to clear the screenshot
            if self.cleaned_data.get(clear_field_name):
                if path_to_delete := final_paths[path_index]:
                    full_path = os.path.join(settings.MEDIA_ROOT, path_to_delete)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                final_paths[path_index] = None  # <-- change to None
                continue

            # upload new file
            if uploaded_file:
                # if there is an old file, delete it
                if old_path := final_paths[path_index]:
                    full_path = os.path.join(settings.MEDIA_ROOT, old_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)

                # save new file
                ext = os.path.splitext(uploaded_file.name)[1]
                file_name = f"{uuid.uuid4().hex}{ext}"  # hex to avoid dashes
                file_path = os.path.join(destination_dir, file_name)

                with open(file_path, "wb+") as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                path_for_json = f"ugc/screenshots/{file_name}"
                final_paths[path_index] = path_for_json

        # save final paths back to the instance (in JSONfield)
        # remove trailing None values
        while final_paths and final_paths[-1] is None:
            final_paths.pop()

        app_instance.screenshots = final_paths

        if commit:
            app_instance.save()

        return app_instance


for i in range(1, settings.SCREENSHOT_COUNT + 1):
    AppScreenshotForm.declared_fields[f"screenshot_{i}"] = forms.ImageField(
        required=False, label=f"Скриншот {i}"
    )
    AppScreenshotForm.declared_fields[f"clear_screenshot_{i}"] = forms.BooleanField(
        required=False, label="Удалить"
    )


class AppCreateForm(forms.ModelForm, CDNTokenValidationMixin):
    upload_screenshots = MultipleFileField(
        widget=MultipleFileInput(
            attrs={
                "multiple": True,
                "id": "inp_scr",
                "class": "action_button",
                "accept": "image/png, image/jpeg",
                "onchange": "previewScreenshots(this)",
            }
        ),
        label=_("FORM_SCREENSHOTS"),
        required=False,
    )

    icon_file = forms.ImageField(
        widget=forms.FileInput(
            attrs={
                "id": "inp_icon",
                "class": "action_button",
                "accept": "image/png, image/jpeg",
                "onchange": "previewIcon(this)",
            }
        ),
        required=False,
    )

    cdn_icon_confirm_token = forms.CharField(widget=forms.HiddenInput(), required=False)
    cdn_screenshots_tokens = forms.CharField(widget=forms.HiddenInput(), required=False)

    cdn_icon_path = forms.CharField(widget=forms.HiddenInput(), required=False)
    cdn_screenshots_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    agree_with_site_rules = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"id": "inp_agree"}),
        label=_("FORM_AGREE_RULES"),
    )

    captcha = CaptchaField(label=_("FORM_CAPTCHA"))

    class Meta:
        model = AppCreateRequests
        _base_names = [
            "category", "title", "slogan", "original_author",
            "developer_site", "description", "requirements"
        ]
        fields = get_translated_fields_list(_base_names)
        widgets = get_translated_widgets_dict({
                    "category": forms.Select(attrs={"class": "input-text", "style": "width: 100%;"}),
                    "title": forms.TextInput(attrs={"class": "input-text"}),
                    "slogan": forms.Textarea(attrs={"class": "brief_intro", "rows": 3, "style": "resize: none;"}),
                    "developer_site": forms.TextInput(attrs={"id": "inp_site", "class": "input-text"}),
                    "description": forms.Textarea(attrs={"class": "brief_intro", "style": "height: 150px; resize: none;"}),
                    "requirements": forms.Textarea(attrs={"class": "brief_intro", "style": "height: 150px; resize: none;"}),
                    "original_author": forms.TextInput(attrs={"class": "input-text"}),
                })

    def clean(self):
        cleaned_data = super().clean()

        # validate icon token
        icon_token = cleaned_data.get("cdn_icon_confirm_token")
        if icon_token:
            decoded = self.validate_cdn_token(icon_token)
            # request path (path) because it's an image
            info = self.get_cdn_file_info(decoded.get("file_id"), fields="path")
            cleaned_data["cdn_icon_path"] = info.get("path") # now path is validated

        # validate screenshots tokens
        scr_tokens_json = cleaned_data.get("cdn_screenshots_tokens")
        if scr_tokens_json:
            try:
                token_list = json.loads(scr_tokens_json)
                safe_paths = []
                for token in token_list:
                    decoded = self.validate_cdn_token(token)
                    info = self.get_cdn_file_info(decoded.get("file_id"), fields="path")
                    if info.get("path"):
                        safe_paths.append(info.get("path"))

                cleaned_data["cdn_screenshots_data"] = safe_paths
            except (json.JSONDecodeError, ValidationError):
                raise ValidationError(_("ERROR_CDN_CHECKSUM_MISMATCH_SCREENSHOTS"))

        return cleaned_data

    def save(self, commit=True):
        app_instance = super().save(commit=False)
        app_instance.user = self.user

        app_instance.icon_path = self.cleaned_data.get("cdn_icon_path")
        app_instance.screenshots = self.cleaned_data.get("cdn_screenshots_data")

        if commit:
            app_instance.save()
        return app_instance

    def get_trans_fields(self):
        flags = {'ru': '🇷🇺 RU', 'en': '🇬🇧 EN', 'be': '🇧🇾 BE', 'uk': '🇺🇦 UK'}
        data = {}
        for field_name in _TRANS_FIELDS:
            data[field_name] = []
            for lang_code, _ in settings.LANGUAGES:
                full_name = f"{field_name}_{lang_code}"
                if full_name in self.fields:
                    data[field_name].append({
                        'code': lang_code,
                        'label': flags.get(lang_code, lang_code.upper()),
                        'input': self[full_name]
                    })
        return data

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)


class AppEditForm(AppCreateForm):
    upload_screenshots = MultipleFileField(
        widget=MultipleFileInput(
            attrs={
                "multiple": True,
                "id": "inp_scr",
                "class": "action_button",
                "accept": "image/png, image/jpeg",
                "onchange": "previewScreenshots(this)",
            }
        ),
        label=_("FORM_SCREENSHOTS"),
        required=False,
    )

    icon_file = forms.ImageField(
        widget=forms.FileInput(
            attrs={
                "id": "inp_icon",
                "class": "action_button",
                "accept": "image/png, image/jpeg",
                "onchange": "previewIcon(this)",
            }
        ),
        required=False,
    )
    cdn_icon_path = forms.CharField(widget=forms.HiddenInput(), required=False)
    cdn_screenshots_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta(AppCreateForm.Meta):
        model = AppEditRequests
        fields = AppCreateForm.Meta.fields
        widgets = AppCreateForm.Meta.widgets

    def __init__(self, target_app=None, *args, **kwargs):
        if target_app:
            kwargs["initial"] = model_to_dict(target_app)
            self.target_app = target_app
        super().__init__(*args, **kwargs)

        self.fields.pop("captcha", None)
        self.fields.pop("agree_with_site_rules", None)

    def save(self, commit=True):
        submission = super().save(commit=False)

        if hasattr(self, "target_app"):
            submission.target_application = self.target_app

            new_icon = self.cleaned_data.get("cdn_icon_path")
            submission.icon_path = new_icon if new_icon else self.target_app.icon_path

            new_scr = self.cleaned_data.get("cdn_screenshots_data")
            submission.screenshots = new_scr if new_scr else self.target_app.screenshots

        if commit:
            submission.save()

        return submission


class AppReportForm(forms.ModelForm):
    class Meta:
        model = AppReportRequests
        fields = ["reason", "description"]
        widgets = {
            "reason": forms.RadioSelect(attrs={"class": "radio_item"}),
            "description": forms.Textarea(
                attrs={"class": "brief_intro", "cols": "500", "name": "whois"}
            ),
            "cols": "500",
            "name": "whois",
        }


class ApplicationAdminForm(forms.ModelForm):
    icon_file = forms.ImageField(
        label=_("ACTION_CHOOSE_ICON"),
        required=False,
        widget=forms.FileInput(attrs={"id": "inp_icon"}),
    )
    screenshots_files = MultipleFileField(
        label=_("FORM_SCREENSHOTS"),
        required=False,
        widget=MultipleFileInput(attrs={"id": "inp_scr", "multiple": True}),
    )

    cdn_icon_path = forms.CharField(widget=forms.HiddenInput(), required=False)
    cdn_screenshots_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Application
        fields = "__all__"

    def save(self, commit=True):
        app_instance = super().save(commit=False)
        new_icon = self.cleaned_data.get("cdn_icon_path")
        if new_icon:
            app_instance.icon_path = new_icon

        scr_data = self.cleaned_data.get("cdn_screenshots_data")
        if scr_data:
            try:
                app_instance.screenshots = json.loads(scr_data)
            except (json.JSONDecodeError, TypeError):
                pass

        if commit:
            app_instance.save()
        return app_instance

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


ALLOWED_EXTENSIONS = ["exe", "zip", "rar", "7z"]


class BaseDistributionForm(forms.ModelForm, CDNTokenValidationMixin):
    cdn_confirm_token = forms.CharField(widget=forms.HiddenInput(), required=False)
    url = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "input-text"}))

    # field for security
    virustotal_url = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "input-text"}))

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.target_dist = kwargs.pop('target_dist', None)  # the target distribution for edit mode
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        cdn_token = cleaned_data.get("cdn_confirm_token")
        url = cleaned_data.get("url")

        # check if there's an existing file (for edit mode)
        has_existing = self.target_dist and (self.target_dist.cdn_file_id or self.target_dist.url)

        if not cdn_token and not url and not has_existing:
            raise ValidationError(_("ERROR_DIST_FORM_NO_FILE_OR_URL"))

        if cdn_token:
            if not cleaned_data.get("virustotal_url"):
                raise ValidationError(_("ERROR_DIST_FORM_NO_VT_LINK"))

            decoded = self.validate_cdn_token(cdn_token)
            file_id = decoded.get("file_id")

            cleaned_data["cdn_file_id"] = file_id

            # go to CDN and get hash
            info = self.get_cdn_file_info(file_id, fields="hash")
            extracted_hash = info.get("hash")
            if not extracted_hash:
                raise ValidationError(_("ERROR_DIST_FORM_CDN_INTO_FAIL"))

            cleaned_data["cdn_hash_extracted"] = extracted_hash
        else:
            if self.target_dist:
                cleaned_data["cdn_file_id"] = self.target_dist.cdn_file_id
                cleaned_data["url"] = url or self.target_dist.url

        return cleaned_data

    def get_trans_fields(self):
        flags = {'ru': '🇷🇺 RU', 'en': '🇬🇧 EN', 'be': '🇧🇾 BE', 'uk': '🇺🇦 UK'}
        data = {}
        fields_to_translate = ["changelog"]

        for field_name in fields_to_translate:
            data[field_name] = []
            for lang_code, _ in settings.LANGUAGES:
                short_code = lang_code.split('-')[0].lower()
                full_name = f"{field_name}_{lang_code}"
                alt_name = f"{field_name}_{short_code}"

                target_field = None
                if full_name in self.fields:
                    target_field = full_name
                elif alt_name in self.fields:
                    target_field = alt_name

                if target_field:
                    data[field_name].append({
                        'code': short_code,
                        'label': flags.get(short_code, short_code.upper()),
                        'input': self[target_field]
                    })
        return data


class DistributionCreateForm(BaseDistributionForm):
    class Meta:
        model = DistributionCreateRequests
        fields = get_translated_fields_list(["version", "url", "changelog"]) + ["virustotal_url"]
        widgets = get_translated_widgets_dict({
            "version": forms.TextInput(attrs={"class": "input-text"}),
            "changelog": forms.Textarea(attrs={"class": "brief_intro", "rows": 3, "style": "resize:none;"}),
        })

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.cdn_file_id = self.cleaned_data.get("cdn_file_id")

        if "cdn_hash_extracted" in self.cleaned_data:
            true_hash = self.cleaned_data["cdn_hash_extracted"]
            instance.cdn_hash = true_hash

        if commit:
            instance.save()
        return instance


class DistributionEditForm(BaseDistributionForm):
    class Meta:
        model = DistributionEditRequests
        fields = get_translated_fields_list(["version", "url", "changelog"]) + ["virustotal_url"]
        widgets = get_translated_widgets_dict({
            "version": forms.TextInput(attrs={"class": "input-text"}),
            "changelog": forms.Textarea(attrs={"class": "brief_intro", "rows": 3, "style": "resize:none;"}),
        })

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.target_distribution = self.target_dist
        instance.user = self.user
        instance.cdn_file_id = self.cleaned_data.get("cdn_file_id")

        # write true hash from CDN
        if "cdn_hash_extracted" in self.cleaned_data:
            true_hash = self.cleaned_data["cdn_hash_extracted"]
            instance.cdn_hash = true_hash

        if commit:
            instance.save()
        return instance
