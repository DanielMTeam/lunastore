import os
from io import BytesIO

from captcha.fields import CaptchaField
from django import forms
from django.contrib import messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .middleware import BlockBannedIP, get_client_ip
from .models import InviteToken, User, UserActivityLog, UserBan
from .validators import validate_invite_limit


class UserBanForm(forms.ModelForm):
    username = forms.CharField(label="Юзернейм", max_length=150)

    class Meta:
        model = UserBan
        fields = ["reason"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.initial["username"] = self.instance.user.username
            self.fields["username"].disabled = True
            self.fields["username"].required = False
        else:
            self.fields["username"].disabled = False
            self.fields["username"].required = True

    def clean_username(self):
        if self.instance and self.instance.pk:
            return self.instance.user

        username = self.cleaned_data["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("user with this username does not exist")
        if UserBan.objects.filter(user=user).exists():
            raise forms.ValidationError("this user is already banned")
        latest_ip = (
            UserActivityLog.objects.filter(user=user).order_by("-timestamp").first()
        )
        if not latest_ip:
            raise forms.ValidationError("cannot ban user without activity log")

        self.found_ip = latest_ip.ip
        self.found_user = user
        return user

    def save(self, commit=True):
        if not self.instance.pk:
            user_to_ban = self.found_user
            ip_to_ban = self.found_ip

            user_to_ban.is_active = False
            user_to_ban.save()
            self.instance.user = user_to_ban
            self.instance.ip = ip_to_ban

        ban_instance = super().save(commit=commit)
        return ban_instance


class UserRegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        if self.request:
            ip = get_client_ip(self.request)
            if ip in BlockBannedIP.get_banned_set():
                raise forms.ValidationError(_("INFO_YOUR_IP_WAS_BANNED"))

    username = forms.CharField(max_length=45, min_length=2)
    email = forms.EmailField(max_length=45)
    captcha = CaptchaField(label="Введите символы с картинки")
    agree_with_site_rules = forms.BooleanField(
        label="Я согласен с правилами сайта и осведомлён о последствиях их нарушения",
        widget=forms.CheckboxInput,
        required=True,
    )
    agree_with_privacy_policy = forms.BooleanField(
        label="Я принимаю условия конфиденциальности",
        widget=forms.CheckboxInput,
        required=True,
    )

    class Meta:
        model = User
        fields = ["username", "email"]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "telegram", "website", "description"]

    username = forms.CharField(
        label="Имя пользователя",
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"class": "input-text", "readonly": "readonly"}),
    )
    telegram = forms.CharField(
        label="Telegram",
        required=False,
        widget=forms.TextInput(attrs={"class": "input-text"}),
    )
    website = forms.URLField(
        label="Веб-сайт",
        required=False,
        widget=forms.URLInput(attrs={"class": "input-text"}),
    )
    discord = forms.CharField(
        label="Discord",
        required=False,
        widget=forms.URLInput(attrs={"class": "input-text"}),
    )
    description = forms.CharField(
        label="Описание профиля",
        required=False,
        widget=forms.Textarea(attrs={"class": "brief_intro", "cols": 90}),
    )
    email = forms.EmailField(
        label="E-mail",
        disabled=True,
        required=False,
        widget=forms.EmailInput(attrs={"class": "input-text", "readonly": "readonly"}),
    )


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input-text"})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input-text"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input-text"})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get("current_password")
        if current_password and not self.user.check_password(current_password):
            raise ValidationError(_("ERROR_CURRENT_PASSWORD_IS_WRONG"))
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get("current_password")
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError(_("ERROR_NEW_PASSWORDS_DONT_MATCH"))

            if current_password and current_password == new_password:
                raise ValidationError(_("ERROR_NEW_PASSWORD_SAME_AS_OLD"))

            password_validation.validate_password(new_password, self.user)

        return cleaned_data


class AvatarUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = []

    avatar = forms.ImageField(
        required=False,
        label=_("ACTION_CHOOSE_FILE"),
        widget=forms.FileInput(attrs={"class": "action_button", "id": "file-upload"}),
        help_text=_("INFO_RECOMENDATIONS_FOR_UPLOAD_AVATAR"),
    )

    confirm_token = forms.CharField(widget=forms.HiddenInput())
    filepath = forms.CharField(widget=forms.HiddenInput())

    client_guard = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            limit_mb = 2
            if avatar.size > limit_mb * 1024 * 1024:
                raise ValidationError(_("INFO_MAXIMUM_AVATAR_SIZE"))

            ext = os.path.splitext(avatar.name)[1].lower()
            valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".jfif"]
            if ext not in valid_extensions:
                raise ValidationError(_("INFO_ACCEPTED_AVATAR_FORMATS"))

            try:
                img = Image.open(avatar)
            except Exception:
                raise ValidationError(_("ERROR_INVALID_IMAGE_FILE"))

            if ext == ".gif":
                return avatar

            target_size = (64, 64)
            width, height = img.size

            if width > target_size[0] or height > target_size[1]:
                img.thumbnail(target_size, Image.Resampling.LANCZOS)

                img_format = "PNG" if ext == ".png" else "JPEG"
                if ext == ".webp":
                    img_format = "WEBP"

                if img_format == "JPEG" and img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background

                buffer = BytesIO()
                img.save(buffer, format=img_format, quality=90)
                new_avatar_name = f"resized_{avatar.name}"
                return ContentFile(buffer.getvalue(), name=new_avatar_name)

        return avatar

    def clean_filepath(self):
        filepath = self.cleaned_data.get("filepath", "")

        if filepath:
            valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".jfif"]

            ext = os.path.splitext(filepath)[1].lower()

            if ext not in valid_extensions:
                raise ValidationError(
                    "Недопустимый формат файла на сервере хранения (CDN). Пожалуйста, обратитесь к администратору."
                )

        return filepath


class DevStatusForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["mail", "github", "about_you", "why_you_choose_us", "username"]

    username = forms.CharField(
        label=_("FORM_DEVSTATUS_YOUR_USERNAME"),
        disabled=True,
        required=False,
        widget=forms.TextInput(attrs={"class": "input-text", "readonly": "readonly"}),
    )

    mail = forms.EmailField(
        label=_("FORM_DEVSTATUS_YOUR_EMAIL"),
        max_length=128,
        widget=forms.EmailInput(attrs={"class": "input-text"}),
        help_text=_("FORM_DEVSTATUS_WE_WILL_CONTACT"),
    )

    github = forms.URLField(
        label=_("FORM_DEVSTATUS_GITHUB"),
        max_length=128,
        widget=forms.URLInput(attrs={"class": "input-text"}),
        help_text=_("FORM_DEVSTATUS_GITHUB_HELP"),
    )

    about_you = forms.CharField(
        label=_("FORM_DEVSTATUS_ABOUT_YOU"),
        max_length=1000,
        widget=forms.Textarea(attrs={"class": "brief_intro", "cols": 90}),
    )

    why_you_choose_us = forms.CharField(
        label=_("FORM_DEVSTATUS_WHY_YOU_CHOOSE"),
        max_length=250,
        widget=forms.Textarea(attrs={"class": "brief_intro", "cols": 90}),
    )

    agree_with_site_rules = forms.BooleanField(
        label=_("FORM_AGREE_RULES"), widget=forms.CheckboxInput, required=True
    )
    agree_with_privacy_policy = forms.BooleanField(
        label=_("FORM_AGREE_POLICY"), widget=forms.CheckboxInput, required=True
    )

    captcha = CaptchaField(label=_("FORM_CAPTCHA"))


# поскольку у django нет стандартного метода добавления пользователя в группу, я это сделал сам лмао (●'◡'●)
class AddToGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        exclude = []

    # add user field
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        # use more normal widget lol
        widget=FilteredSelectMultiple("users", False),
    )

    def __init__(self, *args, **kwargs):
        super(AddToGroupForm, self).__init__(*args, **kwargs)
        # if it is a existing group
        if self.instance.pk:
            # populate the users field with current users in the group
            self.fields["users"].initial = self.instance.user_set.all()

    def save_m2m(self):
        # add the users to the group
        self.instance.user_set.set(self.cleaned_data["users"])

    def save(self, *args, **kwargs):
        # default save
        instance = super(AddToGroupForm, self).save()
        # save many-to-many data
        self.save_m2m()
        return instance


class PasswordConfirmationForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": _("FORM_PASSWORDCONFIRM_ENTER"),
            }
        ),
        label=_("FORM_PASSWORDCONFIRM_CONFIRM"),
        required=True,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        current_password = self.cleaned_data.get("current_password")
        if not self.user.check_password(current_password):
            raise ValidationError(_("ERROR_CURRENT_PASSWORD_IS_WRONG"))
        return current_password


class InviteCodeForm(forms.Form):
    code = forms.CharField(
        label=_("FORM_INVITECODE_TITLE"),
        max_length=12,
        widget=forms.TextInput(
            attrs={
                "id": "code",
                "placeholder": _("FORM_INVITECODE_ENTER"),
                "name": "code",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]
        try:
            invite = InviteToken.objects.get(code=code)
        except InviteToken.DoesNotExist:
            raise ValidationError(_("FORM_INVITECODE_DOESNOTEXIST_ERROR"))

        if invite.is_expired:
            raise ValidationError(_("FORM_INVITECODE_EXPIRED_ERROR"))

        is_limit_ok = validate_invite_limit(invite.owner)

        if not is_limit_ok:
            raise ValidationError(_("FORM_INVITECODE_CODELIMITISNTOK_ERROR"))

        return code


class EmailChangeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["current_email_display"].initial = self.user.email

    current_email_display = forms.EmailField(
        label=_("PAGE_SETTINGS_LABEL_CUR_EMAIL"),
        disabled=True,
        required=False,
        widget=forms.EmailInput(attrs={"class": "input-text", "readonly": "readonly"}),
    )

    new_email = forms.EmailField(
        label=_("PAGE_SETTINGS_LABEL_NEW_EMAIL"),
        widget=forms.EmailInput(attrs={"class": "input-text"}),
    )

    password_check = forms.CharField(
        label=_("PAGE_SETTINGS_LABEL_CUR_PASS"),
        widget=forms.PasswordInput(attrs={"class": "input-text"}),
    )

    def clean_password_check(self):
        password = self.cleaned_data.get("password_check")
        if not self.user.check_password(password):
            raise ValidationError(_("ERROR_CURRENT_PASSWORD_IS_WRONG"))
        return password

    def clean_new_email(self):
        new_email = self.cleaned_data.get("new_email")

        # check, what mail is not same with current
        if self.user and new_email == self.user.email:
            raise ValidationError(_("ERROR_EMAIL_IS_SAME"))

        # check, what mail is not same with another account
        if User.objects.filter(email=new_email).exists():
            raise ValidationError(_("ERROR_EMAIL_ALREADY_EXISTS"))

        return new_email
