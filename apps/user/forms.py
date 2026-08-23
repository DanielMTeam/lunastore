import os
import re
from io import BytesIO
import shutil
from email.mime.image import MIMEImage
from django.conf import settings


from captcha.fields import CaptchaField
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image
from apps.core.utils import force_logout

from .middleware import BlockBannedIP
from apps.core.utils import get_client_ip
from .models import BlacklistedUsername, InviteToken, NoSpamRule, User, UserActivityLog, UserBan
from .utils import get_cached_blacklist
from .tasks import CACHE_KEY
from .validators import validate_invite_limit
from apps.core.mixins import CDNTokenValidationMixin

import threading
import logging
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from constance import config
from django.template import loader
from unfold.widgets import (
    UnfoldAdminIntegerFieldWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminTextInputWidget,
    UnfoldBooleanWidget,
)

logger = logging.getLogger(__name__)


class UserBanForm(forms.ModelForm):
    username = forms.CharField(label="Юзернейм", max_length=150)

    class Meta:
        model = UserBan
        fields = ["reason", "ban_by_ip", "is_permanent", "expires_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.initial["username"] = self.instance.user.username
            self.fields["username"].disabled = True
            self.fields["username"].required = False
        else:
            self.fields["username"].disabled = False
            self.fields["username"].required = True

    def clean(self):
        cleaned_data = super().clean()

        if self.instance and self.instance.pk:
            return cleaned_data

        username = cleaned_data.get("username")
        ban_by_ip = cleaned_data.get("ban_by_ip")
        is_permanent = cleaned_data.get("is_permanent")
        expires_at = cleaned_data.get("expires_at")

        if not is_permanent:
            if not expires_at:
                self.add_error(
                    "expires_at",
                    "Для временной блокировки нужно уточнить время, до которого пользователь будет в блокировке",
                )
            elif expires_at < timezone.now():
                self.add_error(
                    "expires_at",
                    "Дата окончания блокировки не может быть в прошлом")

        if username:
            try:
                user = get_user_model().objects.get(username=username)
            except get_user_model().DoesNotExist:
                self.add_error("username",
                               "Пользователь с таким юзернеймом не найден")
                return cleaned_data

            if UserBan.objects.filter(user=user).exists():
                self.add_error("username", "Этот пользователь уже забанен")
                return cleaned_data

            self.found_user = user
            self.found_ip = None

            if ban_by_ip:
                latest_ip = (
                    UserActivityLog.objects.filter(user=user)
                    .order_by("-timestamp")
                    .first()
                )
                if not latest_ip:
                    self.add_error(
                        "username",
                        "Не удалось найти последний IP пользователя, ибо логов активности нет",
                    )
                    return cleaned_data
                else:
                    self.found_ip = latest_ip.ip

        return cleaned_data

    def save(self, commit=True):
        if not self.instance.pk:
            user_to_ban = self.found_user

            self.instance.user = user_to_ban
            if self.cleaned_data.get("ban_by_ip"):
                self.instance.ip = self.found_ip
            force_logout(user_to_ban)
        ban_instance = super().save(commit=commit)
        cache.delete(CACHE_KEY)
        return ban_instance


class UserRegistrationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.request:
            ip = get_client_ip(self.request)
            if ip in BlockBannedIP.get_banned_set():
                raise forms.ValidationError(_("INFO_YOUR_IP_WAS_BANNED"))
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if not username:
            return username

        banned_records = get_cached_blacklist()

        for record in banned_records:
            if record.is_regex:
                try:
                    if re.search(record.word, username, re.IGNORECASE):
                        raise forms.ValidationError(
                            _("PAGE_ADMIN_APP_MSG_SAVE_ERROR"))
                except re.error:
                    continue
            else:
                if record.word.lower() == username.lower():
                    raise forms.ValidationError(
                        _("PAGE_ADMIN_APP_MSG_SAVE_ERROR"))

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email

        email = email.lower().strip()
        if User.all_objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("ERROR_EMAIL_ALREADY_IN_USE"))

        return email

    username = forms.CharField(max_length=45, min_length=2)
    email = forms.EmailField(max_length=45)
    captcha = CaptchaField(label=_("FORM_CAPTCHA"))
    agree_with_site_rules = forms.BooleanField(
        label=_("FORM_AGREE_RULES"),
        widget=forms.CheckboxInput,
        required=True,
    )
    agree_with_privacy_policy = forms.BooleanField(
        label=_("FORM_AGREE_POLICY"),
        widget=forms.CheckboxInput,
        required=True,
    )

    class Meta:
        model = User
        fields = ["username", "email"]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "telegram",
            "website",
            "description",
            "discord",
            "openvk",
        ]

    username = forms.CharField(
        label=_("FORM_DEVSTATUS_YOUR_USERNAME"),
        required=True,
        widget=forms.TextInput(attrs={"class": "input-text"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance
        if user and user.pk:
            can_change = True
            if user.last_username_change:
                import datetime
                if (timezone.now() - user.last_username_change).days < 365:
                    can_change = False

            if not can_change:
                self.fields["username"].disabled = True
                self.fields["username"].widget.attrs["readonly"] = "readonly"
                import datetime
                next_date = user.last_username_change + \
                    datetime.timedelta(days=365)
                self.fields["username"].help_text = f"Смена юзернейма будет доступна {
                    next_date.strftime('%d.%m.%Y')}."
            else:
                self.fields["username"].help_text = "Внимание: Юзернейм можно менять только 1 раз в год."

    def clean_username(self):
        username = self.cleaned_data.get("username")
        user = self.instance
        if username and user.username != username:
            if user.last_username_change:
                import datetime
                if (timezone.now() - user.last_username_change).days < 365:
                    raise ValidationError(
                        "Юзернейм можно менять только 1 раз в год.")

            if User.objects.filter(
                    username__iexact=username).exclude(
                    pk=user.pk).exists():
                raise ValidationError("Этот юзернейм уже занят.")

            is_blacklisted = False
            for ban in get_cached_blacklist():
                if ban.is_regex:
                    import re
                    if re.search(ban.word, username, re.IGNORECASE):
                        is_blacklisted = True
                        break
                else:
                    if ban.word.lower() == username.lower():
                        is_blacklisted = True
                        break
            if is_blacklisted:
                raise ValidationError("Этот юзернейм запрещен.")

        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        if "username" in self.changed_data:
            user.last_username_change = timezone.now()
        if commit:
            user.save()
        return user
    telegram = forms.CharField(
        label="Telegram",
        required=False,
        max_length=45,
        widget=forms.TextInput(attrs={"class": "input-text"}),
    )
    website = forms.URLField(
        label=_("PAGE_SETTINGS_LABEL_WEBSITE"),
        required=False,
        max_length=45,
        widget=forms.URLInput(attrs={"class": "input-text"}),
    )
    discord = forms.CharField(
        label="Discord",
        required=False,
        max_length=32,
        widget=forms.TextInput(attrs={"class": "input-text"}),
    )
    openvk = forms.CharField(
        label="OpenVK",
        required=False,
        max_length=45,
        widget=forms.TextInput(attrs={"class": "input-text"}),
    )
    description = forms.CharField(
        label=_("PAGE_PROFILESETTINGS_LABEL_BIO"),
        required=False,
        max_length=255,
        widget=forms.Textarea(
            attrs={
                "class": "brief_intro no-md",
                "cols": 90}),
    )
    email = forms.EmailField(
        label="E-mail",
        disabled=True,
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "input-text",
                "readonly": "readonly"}),
    )

    def clean_telegram(self):
        data = self.cleaned_data.get('telegram')
        if data:
            # check for slash or protocol
            if "/" in data or "http" in data:
                raise ValidationError(_("ERROR_PROFILE_TELEGRAM_INVALID"))

            # remove @
            data = data.lstrip('@')
        return data

    def clean_openvk(self):
        data = self.cleaned_data.get('openvk')
        if data:
            if "/" in data or "http" in data:
                raise ValidationError(_("ERROR_PROFILE_OPENVK_INVALID"))
            data = data.lstrip('@')
        return data


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


class AvatarUpdateForm(forms.ModelForm, CDNTokenValidationMixin):
    class Meta:
        model = User
        fields = []

    avatar = forms.ImageField(
        required=False,
        label=_("ACTION_CHOOSE_FILE"),
        widget=forms.FileInput(
            attrs={
                "class": "action_button",
                "id": "file-upload"}),
        help_text=_("INFO_RECOMENDATIONS_FOR_UPLOAD_AVATAR"),
    )

    confirm_token = forms.CharField(widget=forms.HiddenInput(), required=False)
    filepath = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        token = cleaned_data.get("confirm_token")

        if token:
            # validate token (protect from tampering and reuse)
            decoded = self.validate_cdn_token(
                token, expected_type="cdn-confirm")

            # get file info from CDN
            file_id = decoded.get("file_id")
            info = self.get_cdn_file_info(file_id, fields="path")

            if not info or not info.get("path"):
                raise ValidationError(_("ERROR_DIST_FORM_CDN_INFO_FAIL"))

            # save validated data for save() method
            cleaned_data["secure_avatar_id"] = file_id
            cleaned_data["secure_avatar_path"] = info.get("path")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if "secure_avatar_id" in self.cleaned_data:
            instance.avatar_id = self.cleaned_data["secure_avatar_id"]

        if "secure_avatar_path" in self.cleaned_data:
            instance.avatar_path = self.cleaned_data["secure_avatar_path"]

        if commit:
            instance.save()
        return instance


class DevStatusForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "mail",
            "github",
            "about_you",
            "why_you_choose_us",
            "username"]

    username = forms.CharField(
        label=_("FORM_DEVSTATUS_YOUR_USERNAME"),
        disabled=True,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input-text",
                "readonly": "readonly"}),
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


# поскольку у django нет стандартного метода добавления пользователя в
# группу, я это сделал сам лмао (●'◡'●)
class AddToGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        exclude = []

    # add user field
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("Пользователи", is_stacked=False),
        label="Пользователи"
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
        password = self.cleaned_data.get("password")
        if not self.user.check_password(password):
            raise ValidationError(_("ERROR_CURRENT_PASSWORD_IS_WRONG"))
        return password


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
        widget=forms.EmailInput(
            attrs={
                "class": "input-text",
                "readonly": "readonly"}),
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


def send_mail_in_background(subject, body, from_email, to_email, html_email):
    if not config.EMAIL_HOST:
        logger.warning("email host is not configured, skipping email send")
        return

    def str_to_bool(val):
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes", "t", "y")

    use_tls = str_to_bool(config.EMAIL_USE_TLS)
    use_ssl = str_to_bool(config.EMAIL_USE_SSL)

    port = str(config.EMAIL_PORT)
    if port == '587':
        use_tls = True
        use_ssl = False
    elif port == '465':
        use_ssl = True
        use_tls = False
    elif use_ssl and use_tls:
        use_ssl = False  # Fallback to prevent mutual exclusivity error

    try:
        backend = EmailBackend(
            host=config.EMAIL_HOST,
            port=config.EMAIL_PORT,
            username=config.EMAIL_HOST_USER,
            password=config.EMAIL_HOST_PASSWORD,
            use_tls=use_tls,
            use_ssl=use_ssl,
            fail_silently=False,
        )
        email_message = EmailMultiAlternatives(
            subject, body, from_email, [to_email], connection=backend)
        if html_email is not None:
            email_message.attach_alternative(html_email, "text/html")

            logo_path = os.path.join(
                settings.BASE_DIR, 'static', 'img', 'logo_small.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_img = MIMEImage(f.read())
                    logo_img.add_header('Content-ID', '<logo_small.png>')
                    logo_img.add_header('Content-Disposition', 'inline')
                    email_message.attach(logo_img)

        email_message.send()
    except Exception as e:
        logger.error(f"failed to send email: {e}")


class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError(_("ERROR_PASSWORD_RESET_EMAIL_NOT_FOUND"))
        return email

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        if html_email_template_name is not None:
            html_email = loader.render_to_string(
                html_email_template_name, context)
        else:
            html_email = None

        if not from_email:
            from_email = config.DEFAULT_FROM_EMAIL

        # Send asynchronously using threading
        threading.Thread(
            target=send_mail_in_background,
            args=(subject, body, from_email, to_email, html_email)
        ).start()


class NoSpamMassScanForm(forms.Form):
    match_type = forms.ChoiceField(
        label="Тип фильтра",
        choices=[
            choice for choice in NoSpamRule.MatchType.choices
            if choice[0] != NoSpamRule.MatchType.REQUEST_RATE_SIGNAL
        ],
        help_text="По какому признаку искать уже существующих пользователей.",
        widget=UnfoldAdminSelectWidget(),
    )
    pattern = forms.CharField(
        label="Паттерн",
        max_length=255,
        help_text="Домен, regex, CIDR, код страны или диапазон ID (100:500).",
        widget=UnfoldAdminTextInputWidget(),
    )
    action = forms.ChoiceField(
        label="Действие",
        choices=NoSpamRule.RuleAction.choices,
        initial=NoSpamRule.RuleAction.LOG,
        help_text="Сначала рекомендуется «Только лог», затем бан или удаление.",
        widget=UnfoldAdminSelectWidget(),
    )
    reason = forms.CharField(
        label="Причина",
        max_length=255,
        initial="mass noSpam scan",
        help_text="Попадёт в журнал noSpam и в причину бана.",
        widget=UnfoldAdminTextInputWidget(),
    )
    ban_by_ip = forms.BooleanField(
        label="Банить также по последнему IP",
        required=False,
        widget=UnfoldBooleanWidget(),
    )
    is_permanent = forms.BooleanField(
        label="Перманентный бан",
        required=False,
        widget=UnfoldBooleanWidget(),
    )
    ban_duration_minutes = forms.IntegerField(
        label="Длительность бана (мин)",
        min_value=1,
        initial=60,
        required=False,
        widget=UnfoldAdminIntegerFieldWidget(),
    )
    confirm = forms.BooleanField(
        label="Подтверждаю массовое действие",
        required=False,
        help_text="Обязательно для применения бана или удаления.",
        widget=UnfoldBooleanWidget(),
    )

    def __init__(self, *args, **kwargs):
        self.scan_step = kwargs.pop("scan_step", "preview")
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        match_type = cleaned_data.get("match_type")
        pattern = cleaned_data.get("pattern")

        if self.scan_step == "apply" and action in {
            NoSpamRule.RuleAction.BAN,
            NoSpamRule.RuleAction.DELETE,
        } and not cleaned_data.get("confirm"):
            raise ValidationError("Для массового бана или удаления нужно подтверждение.")

        if match_type == NoSpamRule.MatchType.USER_ID_RANGE and pattern:
            from apps.user.services.antispam import AntiSpamService

            try:
                AntiSpamService._parse_user_id_range(pattern)
            except ValueError as exc:
                self.add_error("pattern", str(exc))

        return cleaned_data
