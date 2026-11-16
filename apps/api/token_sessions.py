import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from apps.user.models import APISession, User
from apps.user.services.bans import active_bans


def password_fingerprint(user):
    return salted_hmac("lunastore.api-password", user.password, algorithm="sha256").hexdigest()


def validate_account(user, token=None):
    if not user or not user.is_active or active_bans().filter(user=user).exists():
        raise InvalidToken("Authentication unavailable for this account.")
    if token is not None and not constant_time_compare(
        token.get("password_hash", ""), password_fingerprint(user)
    ):
        raise InvalidToken("Credentials have changed.")


def get_api_session(token, *, lock=False):
    try:
        session_id = uuid.UUID(token.get("api_session", ""))
    except (TypeError, ValueError, AttributeError):
        raise InvalidToken("Invalid API session.")
    sessions = APISession.objects.all()
    if lock:
        sessions = sessions.select_for_update()
    session = sessions.filter(
        pk=session_id, user_id=token.get(api_settings.USER_ID_CLAIM),
        revoked_at__isnull=True, expires_at__gt=timezone.now(),
    ).first()
    if session is None:
        raise InvalidToken("Invalid API session.")
    return session


def token_pair(refresh):
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@transaction.atomic
def issue_tokens(user):
    current_user = User.objects.select_for_update().filter(pk=user.pk).first()
    validate_account(current_user)
    if current_user.password != user.password or (
        current_user.totp_enabled, current_user.totp_secret
    ) != (user.totp_enabled, user.totp_secret):
        raise InvalidToken("Credentials have changed.")
    refresh = RefreshToken()
    refresh[api_settings.USER_ID_CLAIM] = str(user.pk)
    refresh["password_hash"] = password_fingerprint(user)
    session = APISession.objects.create(
        user=user, refresh_jti=refresh[api_settings.JTI_CLAIM],
        expires_at=datetime_from_epoch(refresh["exp"]),
    )
    refresh["api_session"] = str(session.pk)
    return token_pair(refresh)


@transaction.atomic
def rotate_tokens(raw_token):
    refresh = RefreshToken(raw_token)
    session = get_api_session(refresh, lock=True)
    validate_account(User.objects.filter(pk=session.user_id).first(), refresh)
    if session.refresh_jti != refresh[api_settings.JTI_CLAIM]:
        raise InvalidToken("Refresh token has already been used.")
    refresh.set_jti()
    refresh.set_iat()
    refresh.set_exp()
    session.refresh_jti = refresh[api_settings.JTI_CLAIM]
    session.expires_at = datetime_from_epoch(refresh["exp"])
    session.save(update_fields=["refresh_jti", "expires_at"])
    return token_pair(refresh)
