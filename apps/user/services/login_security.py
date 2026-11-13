import hashlib
import time
import unicodedata

import pyotp
from django.core.cache import cache
from django.utils.crypto import constant_time_compare

from apps.core.utils import get_client_ip

TOTP_WINDOW = 300


def increment_window(key, window):
    if cache.add(key, 1, timeout=window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        if cache.add(key, 1, timeout=window):
            return 1
        return cache.incr(key)


def within_limit(key, limit, window):
    digest = hashlib.sha256(key.encode()).hexdigest()
    try:
        return increment_window(f"auth_limit:{digest}", window) <= limit
    except Exception:
        return False


def allow_password_attempt(request, username):
    account = unicodedata.normalize("NFKC", username or "").casefold()
    ip = get_client_ip(request) if request else None
    return within_limit(f"password-ip:{ip}", 60, 600) and within_limit(f"password:{account}", 10, 600)


def allow_totp_attempt(user):
    return within_limit(f"totp:{user.pk}", 5, TOTP_WINDOW)


def verify_totp(user, code):
    if not user.totp_secret or not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    totp = pyotp.TOTP(user.totp_secret)
    step = int(time.time()) // totp.interval
    if not constant_time_compare(totp.generate_otp(step), code):
        return False
    try:
        return bool(cache.add(f"accepted_totp:{user.pk}:{step}", True, timeout=totp.interval * 2))
    except Exception:
        return False


def start_totp_challenge(request, user, next_url):
    request.session.cycle_key()
    request.session["2fa_user_id"] = user.pk
    request.session["2fa_next_url"] = next_url
    request.session["2fa_started_at"] = int(time.time())
    request.session["2fa_failures"] = 0
    request.session["2fa_auth_hash"] = user.get_session_auth_hash()


def clear_totp_challenge(request):
    for key in ("2fa_user_id", "2fa_next_url", "2fa_started_at", "2fa_failures", "2fa_auth_hash"):
        request.session.pop(key, None)
