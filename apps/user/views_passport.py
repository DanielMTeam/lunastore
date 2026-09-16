# lunapassport oauth login / link / unlink views

from __future__ import annotations

import logging
import re
import secrets

from constance import config
from django.contrib import messages
from django.contrib.auth import login as dj_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET, require_POST
from django_smart_ratelimit import ratelimit
from safedelete import HARD_DELETE

from apps.core.tasks import send_notification
from apps.core.utils import get_client_ip
from apps.user.models import LunaPassportLink, User, UserActivityLog, UserBan
from apps.user.services import lunapassport as passport
from apps.user.services.antispam import AntiSpamService, NoSpamContext
from apps.user.tasks import process_login_notification
from apps.user.utils import get_cached_blacklist
from apps.user.validators import validate_email_mx

logger = logging.getLogger(__name__)


def get_real_ip(group, request):
    return get_client_ip(request)


def _should_deny_on_nospam_error() -> bool:
    fail_mode = str(getattr(config, "NOSPAM_FAIL_MODE", "allow")).lower()
    return fail_mode == "deny"


def _run_nospam(
    request,
    entrypoint: str,
    user=None,
    email: str = "",
    username: str = "",
    invite_code: str = "",
    target_user=None,
    target_object=None,
):
    context = NoSpamContext(
        entrypoint=entrypoint,
        ip=get_client_ip(request),
        email=email,
        username=username,
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        invite_code=invite_code,
        user=user,
        extra={"path": request.path},
    )
    try:
        return AntiSpamService.evaluate_and_apply(
            context=context,
            target_user=target_user,
            target_object=target_object,
        )
    except Exception:
        logger.exception("noSpam evaluation failed in passport flow")
        return None


def _require_enabled():
    if not passport.is_enabled():
        raise Http404()


def _safe_next(request, next_url: str | None) -> str | None:
    if not next_url:
        return None
    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def _redirect_after_login(request, next_url: str | None):
    safe = _safe_next(request, next_url)
    if safe:
        return redirect(safe)
    return redirect("home")


def _emails_match(user_email: str, passport_sign_in: str) -> bool:
    return (user_email or "").lower().strip() == (passport_sign_in or "").lower().strip()


def _check_user_ban(user: User) -> str | None:
    ban = UserBan.objects.filter(user=user).first()
    if not ban:
        return None
    if (
        not ban.is_permanent
        and ban.expires_at
        and ban.expires_at <= timezone.now()
    ):
        ban.delete()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return None
    reason = ban.reason
    if not ban.is_permanent and ban.expires_at:
        reason += f" (до {ban.expires_at.strftime('%d.%m.%Y %H:%M')})"
    return reason


def _login_existing_user(request, user: User, next_url: str | None):
    ip = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    if not user.is_active:
        messages.error(request, _("VIEW_LOGIN_INVALID_CREDENTIALS"))
        return redirect("login")

    nospam_decision = _run_nospam(
        request=request,
        entrypoint="login",
        user=user,
        email=user.email,
        username=user.username,
        target_user=user,
    )
    if nospam_decision and nospam_decision.should_block:
        messages.error(request, _("VIEW_LOGIN_INVALID_CREDENTIALS"))
        return redirect("login")
    if nospam_decision is None and _should_deny_on_nospam_error():
        messages.error(request, _("VIEW_LOGIN_INVALID_CREDENTIALS"))
        return redirect("login")

    ban_reason = _check_user_ban(user)
    if ban_reason:
        messages.error(
            request,
            _("VIEW_LOGIN_BANNED_REASON") % {"reason": ban_reason},
        )
        return redirect("login")

    if user.totp_enabled:
        request.session["2fa_user_id"] = user.id
        request.session["2fa_next_url"] = next_url
        return redirect("two_factor_attempt")

    dj_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    UserActivityLog.objects.create(user=user, ip=ip, action="login_passport")
    process_login_notification.enqueue(
        user_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )
    messages.success(
        request,
        _("VIEW_LOGIN_SUCCESS") % {"username": user.username},
    )
    return _redirect_after_login(request, next_url)


def _sanitize_username(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "", (raw or "").lower())
    cleaned = cleaned.strip("._-")[:30]
    if not cleaned:
        cleaned = "passport_user"
    if cleaned[0].isdigit():
        cleaned = f"u_{cleaned}"
    return cleaned[:30]


def _unique_username(base: str) -> str:
    candidate = base
    if not User.objects.filter(username=candidate).exists():
        return candidate
    for _ in range(20):
        suffix = secrets.token_hex(2)
        candidate = f"{base[:24]}_{suffix}"
        if not User.objects.filter(username=candidate).exists():
            return candidate
    return f"pp_{secrets.token_hex(6)}"


def _username_blacklisted(username: str) -> bool:
    blacklist = get_cached_blacklist()
    return any(
        re.search(item.word, username)
        if item.is_regex
        else item.word.lower() in username
        for item in blacklist
    )


def _create_user_from_passport(request, profile: passport.PassportProfile) -> User | None:
    email = profile.sign_in.lower().strip()
    try:
        validate_email_mx(email)
    except ValidationError:
        return None

    # soft-deleted email still occupies unique; user message is set in callback
    if User.objects.all_with_deleted().filter(
        email__iexact=email,
        deleted__isnull=False,
    ).exists():
        logger.info("passport register blocked: soft-deleted email collision")
        return None

    local = email.split("@", 1)[0]
    base = _sanitize_username(local or profile.passport_name or "passport")
    if _username_blacklisted(base):
        base = _sanitize_username(f"user_{secrets.token_hex(3)}")
    username = _unique_username(base)

    nospam_decision = _run_nospam(
        request=request,
        entrypoint="register",
        email=email,
        username=username,
    )
    if nospam_decision and nospam_decision.should_block:
        return None
    if nospam_decision is None and _should_deny_on_nospam_error():
        return None

    user = User(username=username, email=email)
    user.set_unusable_password()
    if profile.passport_name:
        user.first_name = profile.passport_name[:150]
    try:
        user.save()
    except IntegrityError:
        logger.warning("passport register integrity error for email domain user")
        return None

    post = _run_nospam(
        request=request,
        entrypoint="register",
        user=user,
        email=user.email,
        username=user.username,
        target_user=user,
    )
    if post and post.action in ("delete", "ban"):
        return None
    if post is None and _should_deny_on_nospam_error():
        user.delete()
        return None

    try:
        user_group = Group.objects.get(name="Пользователи")
        user.groups.add(user_group)
    except Group.DoesNotExist:
        logger.warning("Group Пользователи not found during Passport register")

    UserActivityLog.objects.create(
        user=user,
        ip=get_client_ip(request),
        action="register_passport",
    )
    send_notification.enqueue(
        user_id=user.id,
        title_key="NOTIF_WELCOME_TITLE",
        content_key="NOTIF_WELCOME_DESCRIPTION",
        meta={"icon": "welcome.png"},
    )
    return user


def _link_to_user(
    user: User,
    profile: passport.PassportProfile,
) -> tuple[LunaPassportLink | None, str | None]:
    # return (link, error_code); revive soft-deleted rows when safe
    try:
        with transaction.atomic():
            existing = LunaPassportLink.objects.all_with_deleted().filter(
                sub=profile.sub,
            ).first()
            if existing:
                if existing.user_id != user.id:
                    return None, "sub_taken"
                if existing.deleted:
                    existing.undelete()
                existing.sign_in = profile.sign_in
                existing.passport_name = profile.passport_name
                existing.save(update_fields=["sign_in", "passport_name"])
                return existing, None

            own = LunaPassportLink.objects.all_with_deleted().filter(
                user=user,
            ).first()
            if own:
                if own.sub != profile.sub:
                    if not own.deleted:
                        return None, "already_linked"
                    # previous soft-deleted unlink left a one-to-one row
                    own.delete(force_policy=HARD_DELETE)
                else:
                    if own.deleted:
                        own.undelete()
                    own.sign_in = profile.sign_in
                    own.passport_name = profile.passport_name
                    own.save(update_fields=["sign_in", "passport_name"])
                    return own, None

            link = LunaPassportLink.objects.create(
                user=user,
                sub=profile.sub,
                sign_in=profile.sign_in,
                passport_name=profile.passport_name,
            )
            return link, None
    except IntegrityError:
        logger.warning("passport link integrity error user_id=%s", user.pk)
        return None, "sub_taken"


def _start_oauth(request, intent: str):
    _require_enabled()
    next_url = request.GET.get("next")
    state = passport.create_state()
    passport.store_oauth_session(
        request,
        state=state,
        intent=intent,
        next_url=next_url,
    )
    return redirect(passport.build_authorize_url(state))


def _apply_pending_bind(request, user: User, *, require_email_match: bool) -> str | None:
    # returns error code or None on success / nothing to do
    profile = passport.get_pending_profile(request)
    if not profile:
        return "no_pending"
    if require_email_match and not _emails_match(user.email, profile.sign_in):
        return "email_mismatch"
    link, err = _link_to_user(user, profile)
    passport.clear_pending_link(request)
    if err:
        return err
    if link is None:
        return "sub_taken"
    return None


@require_GET
def passport_login(request):
    _require_enabled()
    if request.user.is_authenticated:
        return redirect("home")
    return _passport_login_start(request)


@ratelimit(key=get_real_ip, rate="20/10m", block=True)
def _passport_login_start(request):
    return _start_oauth(request, passport.INTENT_LOGIN)


@login_required
@require_GET
def passport_link(request):
    _require_enabled()
    return _passport_link_start(request)


@ratelimit(key=get_real_ip, rate="20/10m", block=True)
def _passport_link_start(request):
    return _start_oauth(request, passport.INTENT_LINK)


@require_GET
def passport_callback(request):
    _require_enabled()
    return _passport_callback_inner(request)


@ratelimit(key=get_real_ip, rate="30/10m", block=True)
def _passport_callback_inner(request):
    returned_state = request.GET.get("state") or ""
    error = request.GET.get("error")
    code = request.GET.get("code")

    intent, next_url = passport.consume_oauth_state(request, returned_state)

    if error:
        desc = request.GET.get("error_description") or error
        messages.error(
            request,
            _("VIEW_PASSPORT_OAUTH_DENIED") % {"detail": desc},
        )
        return redirect(
            "settings_security" if intent == passport.INTENT_LINK else "login"
        )

    if not intent or not code:
        messages.error(request, _("VIEW_PASSPORT_STATE_MISMATCH"))
        return redirect("login")

    access_token = None
    try:
        access_token = passport.exchange_code(code)
        profile = passport.fetch_userinfo(access_token)
    except passport.LunaPassportError:
        messages.error(request, _("VIEW_PASSPORT_TOKEN_FAILED"))
        return redirect("login")
    finally:
        if access_token:
            passport.revoke_token(access_token)

    if intent == passport.INTENT_LINK:
        if not request.user.is_authenticated:
            messages.error(request, _("VIEW_PASSPORT_LINK_LOGIN_REQUIRED"))
            return redirect("login")
        link, err = _link_to_user(request.user, profile)
        if err == "sub_taken":
            messages.error(request, _("VIEW_PASSPORT_SUB_TAKEN"))
        elif err == "already_linked":
            messages.error(request, _("VIEW_PASSPORT_ALREADY_LINKED_OTHER"))
        else:
            messages.success(request, _("VIEW_PASSPORT_LINKED_OK"))
        return redirect("settings_security")

    # intent == login
    if request.user.is_authenticated:
        return redirect("home")

    existing_link = LunaPassportLink.objects.filter(
        sub=profile.sub,
    ).select_related("user").first()
    if existing_link:
        return _login_existing_user(request, existing_link.user, next_url)

    email_owner = User.objects.filter(email__iexact=profile.sign_in).first()
    if email_owner:
        passport.store_pending_link(request, profile)
        messages.warning(request, _("VIEW_PASSPORT_EMAIL_EXISTS_LOGIN"))
        return redirect("login")

    if User.objects.all_with_deleted().filter(
        email__iexact=profile.sign_in,
        deleted__isnull=False,
    ).exists():
        messages.error(request, _("VIEW_PASSPORT_EMAIL_ALREADY_EXISTS"))
        return redirect("login")

    auto_register = bool(getattr(config, "LUNAPASSPORT_AUTO_REGISTER", False))
    if auto_register and config.REGISTRATION_IS_ENABLED:
        if config.INVITES_ON_REGISTER:
            passport.store_pending_link(request, profile)
            messages.warning(request, _("VIEW_PASSPORT_INVITES_REQUIRED"))
            return redirect("login")
        user = _create_user_from_passport(request, profile)
        if not user:
            messages.error(request, _("VIEW_PASSPORT_REGISTER_BLOCKED"))
            return redirect("login")
        _link_to_user(user, profile)
        return _login_existing_user(request, user, next_url)

    passport.store_pending_link(request, profile)
    messages.info(request, _("VIEW_PASSPORT_NEED_ACCOUNT"))
    return redirect("login")


@login_required
@require_POST
def passport_unlink(request):
    _require_enabled()
    link = LunaPassportLink.objects.filter(user=request.user).first()
    if not link:
        messages.info(request, _("VIEW_PASSPORT_NOT_LINKED"))
        return redirect("settings_security")

    if not request.user.has_usable_password():
        messages.error(request, _("VIEW_PASSPORT_UNLINK_NEED_PASSWORD"))
        return redirect("settings_security")

    # hard-delete so unique(sub)/one-to-one can be reused
    link.delete(force_policy=HARD_DELETE)
    messages.success(request, _("VIEW_PASSPORT_UNLINKED_OK"))
    return redirect("settings_security")


@login_required
@require_POST
def passport_confirm_pending(request):
    # confirm binding only when pending email matches the logged-in user
    _require_enabled()
    err = _apply_pending_bind(request, request.user, require_email_match=True)
    if err == "no_pending":
        messages.info(request, _("VIEW_PASSPORT_NO_PENDING"))
    elif err == "email_mismatch":
        passport.clear_pending_link(request)
        messages.error(request, _("VIEW_PASSPORT_EMAIL_MISMATCH"))
    elif err == "sub_taken":
        messages.error(request, _("VIEW_PASSPORT_SUB_TAKEN"))
    elif err == "already_linked":
        messages.error(request, _("VIEW_PASSPORT_ALREADY_LINKED_OTHER"))
    else:
        messages.success(request, _("VIEW_PASSPORT_LINKED_OK"))
    return redirect("settings_security")


def try_auto_bind_pending_after_login(request, user: User) -> None:
    # bind pending passport only when emails match; otherwise drop pending
    if not passport.is_enabled():
        return
    profile = passport.get_pending_profile(request)
    if not profile:
        return
    if not _emails_match(user.email, profile.sign_in):
        passport.clear_pending_link(request)
        return
    err = _apply_pending_bind(request, user, require_email_match=True)
    if err is None:
        messages.success(request, _("VIEW_PASSPORT_LINKED_OK"))
