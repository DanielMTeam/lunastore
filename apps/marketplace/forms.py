import json
import os
import uuid

import jwt
from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.forms.models import model_to_dict
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import (
    AppCreateRequests,
    AppEditRequests,
    Application,
    AppReportRequests,
    Distribution,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def to_python(self, data):
        return data

    def clean(self, data, initial=None):
        if not data and not self.required:
            return None
        return data


class AppScreenshotForm(forms.ModelForm):
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


class AppCreateForm(forms.ModelForm):
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

    agree_with_site_rules = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"id": "inp_agree"}),
        label=_("FORM_AGREE_RULES"),
    )

    captcha = CaptchaField(label=_("FORM_CAPTCHA"))

    class Meta:
        model = AppCreateRequests
        fields = ["category", "title", "slogan", "developer_site", "description"]
        widgets = {
            "category": forms.Select(
                attrs={
                    "class": "input-text",
                    "style": "width: 100%; margin-bottom: 10px;",
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "id": "inp_name",
                    "class": "input-text",
                    "placeholder": _("FORM_APPCREATE_TITLE_EXAMPLE"),
                }
            ),
            "slogan": forms.Textarea(
                attrs={
                    "id": "inp_slogan",
                    "class": "brief_intro",
                    "cols": 140,
                    "rows": 3,
                    "style": "resize: none;",
                }
            ),
            "developer_site": forms.TextInput(
                attrs={"id": "inp_site", "class": "input-text"}
            ),
            "description": forms.Textarea(
                attrs={
                    "id": "inp_desc",
                    "class": "brief_intro",
                    "cols": 100,
                    "style": "height: 150px;",
                }
            ),
        }

    def clean_cdn_screenshots_data(self):
        data = self.cleaned_data.get("cdn_screenshots_data")
        if data:
            try:
                import json

                return json.loads(data)
            except json.JSONDecodeError:
                return []
        return []

    def save(self, commit=True):
        app_instance = super().save(commit=False)

        app_instance.icon_path = self.cleaned_data.get("cdn_icon_path")

        app_instance.screenshots = self.cleaned_data.get("cdn_screenshots_data")

        if commit:
            app_instance.save()
        return app_instance


class AppEditForm(AppCreateForm):
    cdn_icon_path = forms.CharField(widget=forms.HiddenInput(), required=False)
    cdn_screenshots_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta(AppCreateForm.Meta):
        model = AppEditRequests

    def __init__(self, target_app=None, *args, **kwargs):
        if target_app:
            initial_data = model_to_dict(target_app)
            kwargs["initial"] = initial_data
            self.target_app = target_app
        super().__init__(*args, **kwargs)

        if "captcha" in self.fields:
            del self.fields["captcha"]
        if "agree_with_site_rules" in self.fields:
            del self.fields["agree_with_site_rules"]

    def save(self, commit=True):
        submission = super().save(commit=False)

        if hasattr(self, "target_app"):
            submission.target_application = self.target_app

            new_icon = self.cleaned_data.get("cdn_icon_path")
            if new_icon:
                submission.icon_path = new_icon
            elif not submission.icon_path and self.target_app.icon_path:
                submission.icon_path = self.target_app.icon_path

            new_scr = self.cleaned_data.get("cdn_screenshots_data")
            if new_scr:
                import json

                try:
                    submission.screenshots = json.loads(new_scr)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif not submission.screenshots and self.target_app.screenshots:
                submission.screenshots = self.target_app.screenshots

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


class DistributionForm(forms.ModelForm):
    cdn_confirm_token = forms.CharField(widget=forms.HiddenInput(), required=False)
    url = forms.URLField(required=False)

    class Meta:
        model = Distribution
        fields = ["version", "url", "changelog"]
        widgets = {
            "version": forms.TextInput(attrs={"class": "input-text"}),
            "url": forms.URLInput(attrs={"class": "input-text"}),
            "changelog": forms.Textarea(
                attrs={"class": "brief_intro", "rows": 3, "style": "resize:none;"}
            ),
        }

    def save(self, commit=True):
        distribution = super().save(commit=False)

        new_file_id = self.cleaned_data.get("cdn_file_id")
        if new_file_id:
            distribution.cdn_file_id = new_file_id

        if commit:
            distribution.save()
        return distribution

    def clean(self):
        cleaned_data = super().clean()
        cdn_token = cleaned_data.get("cdn_confirm_token")
        url = cleaned_data.get("url")
        has_existing = self.instance and (
            self.instance.cdn_file_id or self.instance.url
        )

        if not cdn_token and not url and not has_existing:
            raise ValidationError(
                _("Нужно загрузить файл или указать ссылку для скачивания")
            )

        if cdn_token:
            try:
                decoded = jwt.decode(
                    cdn_token, settings.LUNASPIRE_SECRET_KEY, algorithms=["HS256"]
                )
                if decoded.get("type") != "cdn-confirm":
                    raise ValidationError(_("Неверный тип токена от CDN."))

                cleaned_data["cdn_file_id"] = decoded.get("file_id")
            except jwt.InvalidTokenError:
                raise ValidationError(
                    _("Ошибка валидации: недействительный токен CDN.")
                )

        return cleaned_data

    def clean_file(self):
        file = self.cleaned_data.get("file")

        if file:
            ext = os.path.splitext(file.name)[1][1:].lower()

            print(f"DEBUG: Uploaded file extension: {ext}")

            if ext not in ALLOWED_EXTENSIONS:
                allowed_str = ", ".join(ALLOWED_EXTENSIONS)
                raise ValidationError(
                    _(
                        "Файлы с расширением .%(ext)s не поддерживаются. Разрешены только: %(allowed)s"
                    )
                    % {"ext": ext, "allowed": allowed_str}
                )

        return file
