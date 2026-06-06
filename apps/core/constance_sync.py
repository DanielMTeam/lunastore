import logging
from typing import Any

from constance.signals import config_updated
from django.conf import settings
from django.dispatch import receiver
from dotenv import set_key

logger = logging.getLogger(__name__)

# constance keys that store boolean values
_BOOL_KEYS: frozenset[str] = frozenset({
    "DEBUG",
    "REGISTRATION_IS_ENABLED",
    "DEVELOPER_REGISTRATION_IS_ENABLED",
    "INVITES_ON_REGISTER",
    "ENABLE_DRM",
    "RATE_LIMIT_ENABLED",
    "TELEGRAM_LOGGER_ENABLED",
    "SENTRY_ENABLED",
})


def _serialize_for_dotenv(key: str, value: Any) -> str:
    """Convert a constance value to a string suitable for .env file."""
    if key in _BOOL_KEYS:
        return "True" if value else "False"
    return str(value)


@receiver(config_updated)
def sync_constance_to_dotenv(
    sender: Any,
    key: str,
    old_value: Any,
    new_value: Any,
    **kwargs: Any,
) -> None:
    """Write constance value back to .env file on every change."""
    dotenv_path = str(settings.BASE_DIR / ".env")
    env_value = _serialize_for_dotenv(key, new_value)
    try:
        set_key(dotenv_path, key, env_value)
        logger.info("Synced constance key %s to .env", key)
    except Exception:
        logger.exception("Failed to sync constance key %s to .env", key)
