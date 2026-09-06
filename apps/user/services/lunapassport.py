# lunapassport oauth 2.0 authorization code client (confidential)

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import requests
from constance import config
from django.http import HttpRequest

logger = logging.getLogger(__name__)

SESSION_STATE_KEY = "lunapassport_oauth_state"
SESSION_INTENT_KEY = "lunapassport_oauth_intent"
SESSION_NEXT_KEY = "lunapassport_oauth_next"
SESSION_PENDING_SUB = "pending_passport_sub"
SESSION_PENDING_SIGN_IN = "pending_passport_sign_in"
SESSION_PENDING_NAME = "pending_passport_name"

INTENT_LOGIN = "login"
INTENT_LINK = "link"

_HTTP_TIMEOUT = 15
_BLOCKED_HOSTS = frozenset({
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
})


# raised when lunapassport oauth exchange fails
class LunaPassportError(Exception):
    pass


@dataclass(frozen=True)
class PassportProfile:
    sub: str
    sign_in: str
    passport_name: str


def _cfg(name: str, default: str = "") -> str:
    return str(getattr(config, name, default) or "").strip()


def _secret_cfg(name: str) -> str:
    # prefer process env so secret is not only in constance admin
    env_val = str(os.getenv(name, "") or "").strip()
    if env_val:
        return env_val
    return _cfg(name)


def is_enabled() -> bool:
    if not bool(getattr(config, "LUNAPASSPORT_ENABLED", False)):
        return False
    try:
        base_url()
    except LunaPassportError:
        return False
    return bool(
        client_id()
        and client_secret()
        and redirect_uri()
    )


def _assert_safe_absolute_url(url: str, *, label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LunaPassportError(f"invalid_{label}_scheme")
    if parsed.username or parsed.password:
        raise LunaPassportError(f"invalid_{label}_userinfo")
    host = (parsed.hostname or "").lower()
    if not host:
        raise LunaPassportError(f"invalid_{label}_host")
    if host in _BLOCKED_HOSTS:
        raise LunaPassportError(f"blocked_{label}_host")
    return url.rstrip("/")


def base_url() -> str:
    raw = _secret_cfg("LUNAPASSPORT_BASE_URL")
    if not raw:
        raise LunaPassportError("missing_base_url")
    return _assert_safe_absolute_url(raw, label="base_url")


def authorize_url() -> str:
    return f"{base_url()}/oauth/authorize"


def token_url() -> str:
    return f"{base_url()}/oauth/token"


def userinfo_url() -> str:
    return f"{base_url()}/oauth/userinfo"


def revoke_url() -> str:
    return f"{base_url()}/oauth/revoke"


def redirect_uri() -> str:
    return _cfg("LUNAPASSPORT_REDIRECT_URI")


def client_id() -> str:
    return _secret_cfg("LUNAPASSPORT_CLIENT_ID")


def client_secret() -> str:
    return _secret_cfg("LUNAPASSPORT_CLIENT_SECRET")


def create_state() -> str:
    return secrets.token_urlsafe(24)


def store_oauth_session(
    request: HttpRequest,
    *,
    state: str,
    intent: str,
    next_url: str | None = None,
) -> None:
    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_INTENT_KEY] = intent
    if next_url:
        request.session[SESSION_NEXT_KEY] = next_url
    else:
        request.session.pop(SESSION_NEXT_KEY, None)


def pop_oauth_session(request: HttpRequest) -> tuple[str | None, str | None, str | None]:
    state = request.session.pop(SESSION_STATE_KEY, None)
    intent = request.session.pop(SESSION_INTENT_KEY, None)
    next_url = request.session.pop(SESSION_NEXT_KEY, None)
    return state, intent, next_url


def store_pending_link(
    request: HttpRequest,
    profile: PassportProfile,
) -> None:
    request.session[SESSION_PENDING_SUB] = profile.sub
    request.session[SESSION_PENDING_SIGN_IN] = profile.sign_in
    request.session[SESSION_PENDING_NAME] = profile.passport_name


def get_pending_profile(request: HttpRequest) -> PassportProfile | None:
    sub = request.session.get(SESSION_PENDING_SUB)
    sign_in = request.session.get(SESSION_PENDING_SIGN_IN)
    if not sub or not sign_in:
        return None
    return PassportProfile(
        sub=sub,
        sign_in=sign_in,
        passport_name=request.session.get(SESSION_PENDING_NAME) or "",
    )


def clear_pending_link(request: HttpRequest) -> None:
    request.session.pop(SESSION_PENDING_SUB, None)
    request.session.pop(SESSION_PENDING_SIGN_IN, None)
    request.session.pop(SESSION_PENDING_NAME, None)


def build_authorize_url(state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id(),
            "redirect_uri": redirect_uri(),
            "state": state,
        }
    )
    return f"{authorize_url()}?{query}"


def exchange_code(code: str) -> str:
    # exchange authorization code for access_token
    try:
        response = requests.post(
            token_url(),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri(),
                "client_id": client_id(),
                "client_secret": client_secret(),
            },
            headers={"Accept": "application/json"},
            timeout=_HTTP_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        logger.exception("LunaPassport token request failed")
        raise LunaPassportError("token_request_failed") from exc

    if response.status_code != 200:
        logger.warning("LunaPassport token error status=%s", response.status_code)
        raise LunaPassportError("invalid_grant")

    try:
        payload = response.json()
    except ValueError as exc:
        raise LunaPassportError("invalid_token_response") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise LunaPassportError("missing_access_token")
    return access_token


def fetch_userinfo(access_token: str) -> PassportProfile:
    try:
        response = requests.get(
            userinfo_url(),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=_HTTP_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        logger.exception("LunaPassport userinfo request failed")
        raise LunaPassportError("userinfo_request_failed") from exc

    if response.status_code != 200:
        logger.warning("LunaPassport userinfo error status=%s", response.status_code)
        raise LunaPassportError("userinfo_failed")

    try:
        data: dict[str, Any] = response.json()
    except ValueError as exc:
        raise LunaPassportError("invalid_userinfo") from exc

    sub = str(data.get("sub") or "").strip()
    sign_in = str(data.get("sign_in") or "").strip().lower()
    passport_name = str(data.get("passport_name") or "").strip()
    if not sub or not sign_in:
        raise LunaPassportError("incomplete_userinfo")

    return PassportProfile(sub=sub, sign_in=sign_in, passport_name=passport_name)


def revoke_token(access_token: str) -> None:
    try:
        requests.post(
            revoke_url(),
            data={"token": access_token},
            timeout=_HTTP_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException:
        logger.exception("LunaPassport revoke failed (ignored)")
    except LunaPassportError:
        # base_url misconfigured after token already used — ignore
        pass
