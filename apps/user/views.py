import io
import re
from multiprocessing.process import active_children

from constance import config
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as dj_login
from django.contrib.auth import logout as dj_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from safedelete import HARD_DELETE
from apps.core.notifications.services import NotificationService
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from .tasks import process_login_notification
from apps.core.tasks import send_notification
from django_smart_ratelimit import ratelimit
import pyotp
import qrcode
import base64

from apps.marketplace.models import Application

from .forms import (
    AvatarUpdateForm,
    DevStatusForm,
    EmailChangeForm,
    InviteCodeForm,
    PasswordChangeForm,
    PasswordConfirmationForm,
    ProfileUpdateForm,
    UserRegistrationForm,
    CustomPasswordResetForm,
)
from django.utils.decorators import method_decorator

@method_decorator(ratelimit(key='ip', rate='5/h', block=True), name='post')
@method_decorator(ratelimit(key='post:email', rate='3/h', block=True), name='post')
class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = "user/password_reset_form.html"
    email_template_name = "user/password_reset_email.html"
    html_email_template_name = "user/password_reset_email_html.html"
    subject_template_name = "user/password_reset_subject.txt"

from .middleware import BlockBannedIP
from apps.core.utils import get_client_ip
from .models import (
    BlacklistedUsername,
    DevRequestsModel,
    InviteToken,
    User,
    UserActivityLog,
    UserBan,
)
from .validators import validate_invite_limit
from .decorators import require_modern_browser


def login(request):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    if ip in BlockBannedIP.get_banned_set():
        return render(
            request, "banned_ip.html", {"admin_email": settings.ADMIN_EMAIL}, status=403
        )

    active_ip_bans = UserBan.objects.filter(ip=ip, ban_by_ip=True)
    for ip_ban in active_ip_bans:
        if ip_ban.is_permanent or (
            ip_ban.expires_at and ip_ban.expires_at > timezone.now()
        ):
            return render(
                request,
                "banned_ip.html",
                {"admin_email": settings.ADMIN_EMAIL},
                status=403,
            )

    if request.user.is_authenticated:
        return redirect("home")

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        username_val = request.POST.get("login") or request.POST.get("username")
        password_val = request.POST.get("password")

        form_data = {"username": username_val, "password": password_val}
        form = AuthenticationForm(request, data=form_data)

        if form.is_valid():
            user = form.get_user()
            ban = UserBan.objects.filter(user=user).first()
            if ban:
                if (
                    not ban.is_permanent
                    and ban.expires_at
                    and ban.expires_at <= timezone.now()
                ):
                    ban.delete()
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                else:
                    reason = ban.reason
                    if not ban.is_permanent:
                        exp_str = ban.expires_at.strftime("%d.%m.%Y %H:%M")
                        reason += f" (до {exp_str})"

                    error_msg = _("VIEW_LOGIN_BANNED_REASON") % {"reason": reason}
                    messages.error(request, error_msg)
                    return render(request, "login_splash.html", {"next": next_url})

            if user.totp_enabled:
                request.session["2fa_user_id"] = user.id
                request.session["2fa_next_url"] = next_url
                return redirect("two_factor_attempt")

            dj_login(request, user)

            UserActivityLog.objects.create(user=user, ip=ip, action="login_save_ip")

            process_login_notification.enqueue(
                user_id=user.id,
                ip=ip,
                user_agent=user_agent
            )

            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            messages.success(
                request, _("VIEW_LOGIN_SUCCESS") % {"username": user.username}
            )
            return redirect("home")
        else:
            messages.error(request, _("VIEW_LOGIN_INVALID_CREDENTIALS"))

    return render(request, "login_splash.html", {"next": next_url})


def logout(request):
    dj_logout(request)
    return redirect("/index.php")

@ratelimit(key='ip', rate='10/10m', block=True)
def register(request):
    invite_obj = None

    if not config.REGISTRATION_IS_ENABLED:
        if request.user.is_authenticated:
            return redirect("home")
        return render(request, "register.html")

    if config.INVITES_ON_REGISTER:
        invite_code = request.session.get("allowed_invite_code")

        if not invite_code:
            return redirect("invite_code")

        try:
            invite_obj = InviteToken.objects.get(code=invite_code)
        except InviteToken.DoesNotExist:
            del request.session["allowed_invite_code"]
            return redirect("invite_code")

    if request.method == "POST":
        if request.user.is_authenticated:
            return redirect("home")
        ip = get_client_ip(request)
        active_ip_bans = UserBan.objects.filter(ip=ip, ban_by_ip=True)
        for ip_ban in active_ip_bans:
            if ip_ban.is_permanent or (
                ip_ban.expires_at and ip_ban.expires_at > timezone.now()
            ):
                return render(
                    request,
                    "banned_ip.html",
                    {"admin_email": settings.ADMIN_EMAIL},
                    status=403,
                )
        raw_username = request.POST.get("username", "").lower().strip()
        blacklist = BlacklistedUsername.objects.all()
        is_blocked = False

        is_blocked = any(
            re.search(item.word, raw_username)
            if item.is_regex
            else item.word.lower() in raw_username
            for item in blacklist
        )
        if is_blocked:
            return redirect("502_error")
        form = UserRegistrationForm(request.POST, request=request)
        if form.is_valid():
            if config.INVITES_ON_REGISTER and invite_obj:
                if not validate_invite_limit(invite_obj.owner):
                    return redirect("invite_code")
            user = form.save(commit=False)
            if invite_obj:
                user.invited_by = invite_obj.owner
            user.save()
            if config.INVITES_ON_REGISTER:
                request.session.pop("allowed_invite_code", None)
            user_group = Group.objects.get(name="Пользователи")
            user.groups.add(user_group)
            UserActivityLog.objects.create(
                user=user, ip=get_client_ip(request), action="register_save_ip"
            )
            user.backend = "django.contrib.auth.backends.ModelBackend"
            dj_login(request, user)
            send_notification.enqueue(
                user_id=user.id,
                title_key="NOTIF_WELCOME_TITLE",
                content_key="NOTIF_WELCOME_DESCRIPTION",
                meta={"icon": "welcome.png"}
            )
            return redirect("home")
    else:
        if request.user.is_authenticated:
            return redirect("home")
        form = UserRegistrationForm(request=request)
    return render(request, "register_on.html", {"form": form, "invite_obj": invite_obj})


def profile(request):
    id = request.GET.get("id")

    if id:
        obj = get_object_or_404(User, id=id)
    else:
        if not request.user.is_authenticated:
            raise Http404(
                "No ID provided and you (maybe; or you just have a problem with your cookie) is anonymous"
            )
        obj = get_object_or_404(User, id=request.user.id)
    apps_count = Application.objects.filter(user=obj).count()
    badges = [tag.strip() for tag in obj.badges.split(";")] if obj.badges else []
    active_ban = None
    ban_record = UserBan.objects.filter(user=obj).first()
    if ban_record:
        if ban_record.is_permanent or (
            ban_record.expires_at and ban_record.expires_at > timezone.now()
        ):
            active_ban = ban_record
        else:
            ban_record.delete()
            obj.is_active = True
            obj.save(update_fields=["is_active"])
    from apps.marketplace.models import Review
    from django.core.paginator import Paginator
    
    act = request.GET.get("act")
    reviews_page = None
    recent_reviews = None
    
    if act == "show_reviews":
        reviews_list = Review.objects.filter(user=obj).order_by('-created_at')
        paginator = Paginator(reviews_list, 5)
        page_number = request.GET.get("page")
        reviews_page = paginator.get_page(page_number)
    else:
        recent_reviews = Review.objects.filter(user=obj).order_by('-created_at')[:5]
        
    return render(
        request,
        "profile.html",
        context={
            "obj": obj, 
            "apps_count": apps_count, 
            "active_ban": active_ban, 
            "badges": badges,
            "act": act,
            "reviews_page": reviews_page,
            "recent_reviews": recent_reviews
        },
    )


@login_required
def profile_settings(request):
    user = request.user
    forms = {
        "profile_form": ProfileUpdateForm(instance=user),
        "password_form": PasswordChangeForm(user=user),
        "avatar_form": AvatarUpdateForm(instance=user),
        "del_acc_form": PasswordConfirmationForm(user=user),
        "email_form": EmailChangeForm(user=user),
        "cdn_base_url": getattr(request, 'geo_domains', {}).get('SPIRE_URL', settings.LUNASPIRE_URL),
        "api_base_url": getattr(request, 'geo_domains', {}).get('API_URL', settings.API_URL),
        "is_developer": request.user.groups.filter(name="Разработчики").exists(),
        "dev_status_enabled": config.DEVELOPER_REGISTRATION_IS_ENABLED,
    }
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "profile":
            forms["profile_form"] = ProfileUpdateForm(request.POST, instance=user)
            if forms["profile_form"].is_valid():
                forms["profile_form"].save()
                messages.success(request, _("INFO_PROFILE_IS_UPDATED"))
                return redirect("settings")
            else:
                for field, errors in forms["profile_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)
        elif form_type == "password":
            forms["password_form"] = PasswordChangeForm(request.POST, user=user)
            if forms["password_form"].is_valid():
                user.set_password(forms["password_form"].cleaned_data["new_password"])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, _("INFO_PASSWORD_WAS_CHANGED"))
                return redirect("settings")
            else:
                for field, errors in forms["password_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)
        elif form_type == "avatar":
            # initialize form
            forms["avatar_form"] = AvatarUpdateForm(request.POST, request.FILES, instance=user)

            if forms["avatar_form"].is_valid():
                forms["avatar_form"].save()

                messages.success(request, _("INFO_AVATAR_WAS_UPLOADED"))
                return redirect("settings")
            else:
                # print errors via messages.error form
                for field, errors in forms["avatar_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)
        elif form_type == "init_delete":
            request.session["can_view_delete_page"] = True
            return redirect("delete_account")
        elif form_type == "email":
            forms["email_form"] = EmailChangeForm(request.POST, user=user)
            if forms["email_form"].is_valid():
                user.email = forms["email_form"].cleaned_data["new_email"]
                user.save()
                messages.success(request, _("INFO_EMAIL_WAS_CHANGED"))
                return redirect("settings")
            else:
                for field, errors in forms["email_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)
    return render(request, "settings.html", forms)


@login_required
def dev_status(request):
    user = request.user
    is_developer = request.user.groups.filter(name="Разработчики").exists()
    has_pending_request = DevRequestsModel.objects.filter(user=request.user).exists()
    # initialize the form
    if request.method == "POST":
        form = DevStatusForm(request.POST, instance=user)
        if form.is_valid():
            # save model data
            form.save()
            # get cleaned data
            cd = form.cleaned_data

            # create DevRequestsModel entry
            DevRequestsModel.objects.create(
                user=user,
                github=cd.get("github"),
                mail=cd.get("mail"),
                about_you=cd.get("about_you"),
                why_you_choose_us=cd.get("why_you_choose_us"),
            )

            messages.success(request, _("INFO_APP_CREATE_REQUEST_WAS_SENT"))
            return redirect("home")
    else:
        form = DevStatusForm(instance=user)

    # render the template with the form
    return render(
        request,
        "dev_add.html",
        {
            "dev_request_form": form,
            "is_developer": is_developer,
            "has_pending_request": has_pending_request,
            "registration_enabled_status": config.DEVELOPER_REGISTRATION_IS_ENABLED,
        },
    )


def critical_error(request):
    return render(request, "502.html")


@login_required
def delete_account(request):
    if not request.session.get("can_view_delete_page"):
        messages.warning(request, _("ERROR_ACCESS_DENIED_PROFILE"))
        return redirect("settings")
    if request.method == "POST":
        form = PasswordConfirmationForm(request.user, request.POST)
        if form.is_valid():
            request.user.delete(force_policy=HARD_DELETE)
            logout(request)
            messages.success(request, _("INFO_ACCOUNT_WAS_DELETED"))
            return redirect("home")
    else:
        form = PasswordConfirmationForm(request.user)
    apps_loaded_count = Application.objects.filter(user=request.user).count()
    invites = User.objects.filter(invited_by=request.user)
    return render(
        request,
        "del_acc.html",
        {"apps_count": apps_loaded_count, "form": form, "invites": invites},
    )


@login_required
def invite_person(request):
    invite, created = InviteToken.objects.get_or_create(owner=request.user)
    invited_users_list = request.user.invited_users.all().order_by("-date_joined")
    
    from datetime import timedelta
    from django.utils import timezone
    
    time_threshold = timezone.now() - timedelta(days=int(config.MAX_INVITE_DAYS_LIMIT))
    recent_invites = request.user.invited_users.filter(
        date_joined__gte=time_threshold
    ).order_by("date_joined")
    
    recent_count = recent_invites.count()
    max_limit = int(config.MAX_INVITE_USES_COUNT)
    remaining_invites = max(0, max_limit - recent_count)
    
    can_invite = remaining_invites > 0
    next_invite_date = None
    
    if not can_invite and recent_invites.exists():
        oldest_recent = recent_invites.first()
        next_invite_date = oldest_recent.date_joined + timedelta(days=int(config.MAX_INVITE_DAYS_LIMIT))
    
    limit_info_text = _("PAGE_INVITE_LIMIT_INFO") % {
        "limit": remaining_invites,
        "days": config.MAX_INVITE_DAYS_LIMIT
    }
    
    return render(
        request,
        "invite.html",
        {
            "invite_code": invite.refresh_code_if_expired(),
            "invited_users": invited_users_list,
            "limit_info_text": limit_info_text,
            "can_invite": can_invite,
            "next_invite_date": next_invite_date,
        },
    )


def invite_code(request):
    if not config.REGISTRATION_IS_ENABLED:
        return render(request, "register.html")
    if not config.INVITES_ON_REGISTER:
        return redirect("home")
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = InviteCodeForm(request.POST)
        if form.is_valid():
            request.session["allowed_invite_code"] = form.cleaned_data["code"]
            request.session.modified = True
            request.session.save()
            return redirect("register")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = InviteCodeForm()

    return render(request, "invite_input.html", {"form": form})


@login_required
@require_modern_browser
def notifications(request):
    api_url = getattr(request, 'geo_domains', {}).get('SPIRE_URL', settings.LUNASPIRE_URL)
    if not api_url.startswith('http'):
        api_url = f"http://{api_url}"

    meta = NotificationService.get_notifications_meta(request.user.id)
    total_items = meta['total']

    dummy_list = range(total_items)
    paginator = Paginator(dummy_list, 10)

    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    page_range = paginator.get_elided_page_range(
        page_obj.number, on_each_side=1, on_ends=1
    )

    # get or create notification token for the user
    context = {
        'page_obj': page_obj,
        'page_range': page_range,
        'total_unread': meta.get('total_unread', 0),
        'notify_token': NotificationService.get_receive_token(request.user.id),
        'api_url': api_url,
    }
    return render(request, "notifications.html", context)


def two_factor_attempt(request):
    user_id = request.session.get("2fa_user_id")
    next_url = request.session.get("2fa_next_url")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        code = request.POST.get("2fa-code")
        if code and user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(code):
                dj_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                ip = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                UserActivityLog.objects.create(user=user, ip=ip, action="login_save_ip")
                process_login_notification.enqueue(
                    user_id=user.id,
                    ip=ip,
                    user_agent=user_agent
                )
                del request.session["2fa_user_id"]
                if "2fa_next_url" in request.session:
                    del request.session["2fa_next_url"]

                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                messages.success(request, _("VIEW_LOGIN_SUCCESS") % {"username": user.username})
                return redirect("home")
            else:
                messages.error(request, _("ERROR_2FA_INVALID_CODE"))
                return redirect("two_factor_attempt")
    
    return render(request, "2fa_attempt.html")


from .models import UserSession
from django.utils import timezone
from datetime import timedelta

@login_required
def settings_security(request):
    user = request.user
    forms = {
        "password_form": PasswordChangeForm(user=user),
        "email_form": EmailChangeForm(user=user),
        "user": user,
        "active_sessions": UserSession.objects.filter(user=user),
        "current_session_key": request.session.session_key,
        "is_new_session": False,
    }
    
    current_session = UserSession.objects.filter(session_key=request.session.session_key).first()
    if current_session and (timezone.now() - current_session.created_at).total_seconds() < 86400:
        forms["is_new_session"] = True

    if request.method == "POST":
        if forms["is_new_session"]:
            messages.error(request, "Ваше устройство (сессия) новое. В целях безопасности смена почты и пароля недоступны первые 24 часа.")
            return redirect("settings_security")
            
        form_type = request.POST.get("form_type")
        if form_type == "password":
            forms["password_form"] = PasswordChangeForm(request.POST, user=user)
            if forms["password_form"].is_valid():
                user.set_password(forms["password_form"].cleaned_data["new_password"])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, _("INFO_PASSWORD_WAS_CHANGED"))
                return redirect("settings_security")
            else:
                for field, errors in forms["password_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)
        elif form_type == "email":
            forms["email_form"] = EmailChangeForm(request.POST, user=user)
            if forms["email_form"].is_valid():
                user.email = forms["email_form"].cleaned_data["new_email"]
                user.save()
                messages.success(request, _("INFO_EMAIL_WAS_CHANGED"))
                return redirect("settings_security")
            else:
                for field, errors in forms["email_form"].errors.items():
                    for error in errors:
                        messages.error(request, error)

    return render(request, "settings_security.html", forms)


@login_required
def settings_2fa_set(request):
    user = request.user
    
    current_session = UserSession.objects.filter(session_key=request.session.session_key).first()
    if current_session and (timezone.now() - current_session.created_at).total_seconds() < 86400:
        messages.error(request, "Ваше устройство (сессия) новое. Управление 2FA недоступно первые 24 часа.")
        return redirect("settings_security")

    if not request.session.get("2fa_sudo_mode"):
        if request.method == "POST":
            password = request.POST.get("password")
            if user.check_password(password):
                request.session["2fa_sudo_mode"] = True
                return redirect("settings_2fa_set")
            else:
                messages.error(request, _("ERROR_2FA_INVALID_PASSWORD"))
                return redirect("settings_2fa_set")
        return render(request, "2fa_password_confirm.html")

    if request.method == "POST":
        if request.POST.get("disable") == "1" and user.totp_enabled:
            user.totp_enabled = False
            user.totp_secret = None
            user.save()
            messages.success(request, _("INFO_2FA_DISABLED"))
            del request.session["2fa_sudo_mode"]
            return redirect("settings_security")

        code = request.POST.get("2fa-code")
        secret_key = request.session.get("2fa_pending_secret")
        if code and secret_key:
            totp = pyotp.TOTP(secret_key)
            if totp.verify(code):
                user.totp_secret = secret_key
                user.totp_enabled = True
                user.save()
                messages.success(request, _("INFO_2FA_ENABLED"))
                del request.session["2fa_sudo_mode"]
                if "2fa_pending_secret" in request.session:
                    del request.session["2fa_pending_secret"]
                return redirect("settings_security")
            else:
                messages.error(request, _("ERROR_2FA_INVALID_CODE"))
                return redirect("settings_2fa_set")

    context = _get_2fa_setup_context(request)
    return render(request, "2fa_set.html", context)


def revert_impersonation(request):
    admin_id = request.session.get("impersonated_by")
    if admin_id:
        admin_user = get_object_or_404(User, id=admin_id)
        if admin_user.is_staff:
            dj_login(request, admin_user, backend="django.contrib.auth.backends.ModelBackend")
            if "impersonated_by" in request.session:
                del request.session["impersonated_by"]
                
            host = request.get_host()
            if ":9088" in host:
                host = host.replace(":9088", ":8088")
            
            admin_path = getattr(settings, "ADMIN_URL", "admin")
            # If ADMIN_URL has HTTP:// inside it, it's a full URL.
            # In settings: ADMIN_URL = "lunas-office" or full URL.
            # wait, in settings.py: ADMIN_URL = os.getenv("ADMIN_URL", "admin")
            if admin_path.startswith("http"):
                admin_url = f"{admin_path}/user/user/"
            else:
                admin_url = f"{request.scheme}://{host}/{admin_path}/user/user/"
                
            return redirect(admin_url)
    return redirect("home")


def _get_2fa_setup_context(request):
    user = request.user
    if user.totp_enabled:
        return {"is_enabled": True}
    
    secret = request.session.get("2fa_pending_secret")
    if not secret:
        secret = pyotp.random_base32()
        request.session["2fa_pending_secret"] = secret
        
    totp_auth_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name="LunaStore"
    )
    
    qr = qrcode.make(totp_auth_url)
    buffered = io.BytesIO()
    qr.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return {
        "is_enabled": False,
        "secret_key": secret,
        "qr_code_base64": qr_code_base64
    }

from django.contrib.sessions.models import Session

@login_required
def terminate_session(request, session_pk):
    current_session = UserSession.objects.filter(session_key=request.session.session_key).first()
    if current_session and (timezone.now() - current_session.created_at).total_seconds() < 86400:
        messages.error(request, "Ваше устройство (сессия) новое. Управление сеансами недоступно первые 24 часа.")
        return redirect("settings_security")

    user_session = get_object_or_404(UserSession, pk=session_pk, user=request.user)
    
    # Do not allow terminating the current session this way
    if user_session.session_key == request.session.session_key:
        messages.error(request, "Нельзя завершить текущую сессию отсюда. Воспользуйтесь выходом.")
        return redirect("settings_security")
        
    try:
        # Delete from Django session store
        Session.objects.filter(session_key=user_session.session_key).delete()
    except Exception:
        pass
        
    user_session.delete()
    messages.success(request, "Сеанс успешно завершен.")
    return redirect("settings_security")
