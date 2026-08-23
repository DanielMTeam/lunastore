from datetime import timedelta
from unfold.contrib.constance.settings import UNFOLD_CONSTANCE_ADDITIONAL_FIELDS
from sentry_sdk.integrations.logging import LoggingIntegration
import sentry_sdk
import logging
import os
import sys
from pathlib import Path

from django.templatetags.static import static
from dotenv import load_dotenv
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# sentry/glitchtip error tracking

SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "False") == "True"
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_TRACES_SAMPLE_RATE = float(
    os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2"))
SENTRY_PROFILES_SAMPLE_RATE = float(
    os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production")

# optional clickhouse analytics (disabled by default)
ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "False") == "True"
CLICKHOUSE_HOST = os.getenv(
    "CLICKHOUSE_HOST",
    "clickhouse" if (os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER")) else "127.0.0.1",
)
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "analytics")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv(
    "CLICKHOUSE_DATABASE",
    "lunastore_analytics",
)
CLICKHOUSE_SECURE = os.getenv("CLICKHOUSE_SECURE", "False") == "True"

if SENTRY_ENABLED and SENTRY_DSN:
    _sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=True,
        environment=SENTRY_ENVIRONMENT,
        release=os.getenv("VERSION", "2.1"),
        integrations=[_sentry_logging],
    )

# PLEASE, do not change this, if you don't understand what you do
VERSION = os.getenv("VERSION", "2.7")

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

GEOIP_PATH = BASE_DIR / 'apps' / 'core' / 'geolocation'
GEOIP_CITY = 'geo.mmdb'
GEOIP_COUNTRY = 'geo.mmdb'

ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:8000")

LOGIN_URL = "login.php"

# global rate limit settings
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "False") == "True"
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "50"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "35"))

# drf api throttle defaults (overridable live via constance)
API_THROTTLE_ENABLED = os.getenv("API_THROTTLE_ENABLED", "True") == "True"
API_THROTTLE_ANON_RATE = os.getenv("API_THROTTLE_ANON_RATE", "1000/hour")
API_THROTTLE_USER_RATE = os.getenv("API_THROTTLE_USER_RATE", "5000/hour")

# redis configuration
REDIS_HOST = os.getenv(
    "REDIS_HOST",
    "redis" if (os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER")) else "127.0.0.1",
)
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

# django-smart-ratelimit (ratelimit for functions)
RATELIMIT_BACKEND = os.getenv("RATELIMIT_BACKEND", "redis")
RATELIMIT_REDIS = {
    'host': REDIS_HOST,
    'port': REDIS_PORT,
    'db': REDIS_DB,
}

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

LOGIN_REDIRECT_URL = "/index.php"

LOGOUT_REDIRECT_URL = "/login.php"

DEBUG = os.getenv("DEBUG", "False") == "True"

TELEGRAM_LOGGER_ENABLED = os.getenv(
    "TELEGRAM_LOGGER_ENABLED",
    "False") == "True"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_LOG_CHAT_ID = os.getenv("TELEGRAM_LOG_CHAT_ID", "")
TELEGRAM_LOG_TOPIC_ID = os.getenv("TELEGRAM_LOG_TOPIC_ID", "")

LUNASPIRE_SECRET_KEY = os.getenv("LUNASPIRE_SECRET_KEY")
LUNASPIRE_URL = os.getenv("LUNASPIRE_URL", "spire.lunastore.app")
API_URL = os.getenv("API_URL", "api.lunastore.app")

ADMIN_URL = os.getenv("ADMIN_URL", "admin")

CORS_ALLOW_CREDENTIALS = True

# empty cookie domain in debug/ci so localhost/testserver work
_default_cookie_domain = "" if DEBUG else ".lunastore.app"
SESSION_COOKIE_DOMAIN = os.getenv(
    "SESSION_COOKIE_DOMAIN",
    _default_cookie_domain) or None
CSRF_COOKIE_DOMAIN = os.getenv(
    "CSRF_COOKIE_DOMAIN",
    _default_cookie_domain) or None

LUNASPIRE_URL_WITHOUT_PROTO = os.getenv(
    "LUNASPIRE_URL_WITHOUT_PROTO", "spire.lunastore.app"
)

# semicolon-separated lists: drop empty segments (corsheaders rejects "")
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(";")
    if o.strip()
]

if not DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CORS_ALLOW_ALL_ORIGINS = False
    SESSION_COOKIE_SAMESITE = None
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
else:
    CORS_ALLOW_ALL_ORIGINS = False

SECRET_KEY = os.getenv("SECRET_KEY")

ALLOWED_HOSTS = [host.strip() for host in os.getenv(
    "ALLOWED_HOSTS", "").split(";") if host.strip()]

# cidr/ip list of reverse proxies allowed to set client ip headers
TRUSTED_PROXIES = [
    p.strip() for p in os.getenv("TRUSTED_PROXIES", "").split(";") if p.strip()
]

CSRF_TRUSTED_ORIGINS = [
    c.strip() for c in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "").split(";") if c.strip()]

# MOTD List of site (you can see that in the header)
MOTD_LIST = [
    msg.strip() for msg in os.getenv("MOTD_LIST", "").split(";") if msg.strip()
]

STATIC_ROOT = BASE_DIR / "static"

ENABLE_DRM = os.getenv("ENABLE_DRM", "False")

# Application definition

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

INSTALLED_APPS = [
    "django.forms",
    "modeltranslation",
    "django.contrib.auth",
    "mozilla_django_oidc",  # openid
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.marketplace.apps.MarketplaceConfig",
    "apps.user.apps.UserConfig",
    "apps.core.apps.CoreConfig",
    "apps.terms.apps.TermsConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "captcha",
    # custom admin panel frontend
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardian",
    "unfold.contrib.simple_history",
    "unfold.contrib.location_field",
    "unfold.contrib.constance",
    "constance",
    "django.contrib.admin",
    "django_cleanup.apps.CleanupConfig",
    "django.contrib.postgres",
    "rest_framework",
    "apps.api.apps.APIConfig",
    "drf_spectacular",
    "corsheaders",
    "django_extensions",
    'django_user_agents',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.api.handlers.luna_exception_handler",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        # 'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.api.authentication.CustomJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.api.throttling.RealIPAnonRateThrottle",
        "apps.api.throttling.RealIPUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": API_THROTTLE_ANON_RATE,
        "user": API_THROTTLE_USER_RATE,
    },
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer', 'Token'),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "LunaStore API",
    "DESCRIPTION": "API Documentation for LunaStore",
    "VERSION": VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
}


# tasks configuration

TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}

if 'test' in sys.argv:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
            }
        }
    }


# django-constance configuration
# backend: Redis (same instance as cache)
CONSTANCE_BACKEND = "constance.backends.redisd.RedisBackend"
CONSTANCE_REDIS_CONNECTION = REDIS_URL

CONSTANCE_ADDITIONAL_FIELDS = {
    **UNFOLD_CONSTANCE_ADDITIONAL_FIELDS,
    "textarea": [
        "django.forms.CharField",
        {
            "widget": "unfold.widgets.UnfoldAdminTextareaWidget",
            "required": False,
        },
    ],
}

# all values from .env with os.getenv() defaults
CONSTANCE_CONFIG = {
    # -- django core --
    "VERSION": (
        os.getenv("VERSION", "2.1"),
        "Версия приложения",
        str,
    ),
    "DEBUG": (
        os.getenv("DEBUG", "False") == "True",
        "Режим отладки (требует перезагрузки)",
        bool,
    ),
    "SECRET_KEY": (
        os.getenv("SECRET_KEY", ""),
        "Django SECRET_KEY (требует перезагрузки)",
        str,
    ),
    "ADMIN_URL": (
        os.getenv("ADMIN_URL", "admin"),
        "URL-префикс админ-панели (требует перезагрузки)",
        str,
    ),
    "ADMIN_EMAIL": (
        os.getenv("ADMIN_EMAIL", ""),
        "Email администратора",
        str,
    ),
    # -- hosts and origins (require restart) --
    "ALLOWED_HOSTS": (
        os.getenv("ALLOWED_HOSTS", ""),
        "Разрешённые хосты через ; (требует перезагрузки)",
        "textarea",
    ),
    "CORS_ALLOWED_ORIGINS": (
        os.getenv("CORS_ALLOWED_ORIGINS", ""),
        "CORS-источники через ; (требует перезагрузки)",
        "textarea",
    ),
    "CSRF_TRUSTED_ORIGINS": (
        os.getenv("CSRF_TRUSTED_ORIGINS", ""),
        "CSRF trusted origins через ; (требует перезагрузки)",
        "textarea",
    ),
    "SESSION_COOKIE_DOMAIN": (
        os.getenv("SESSION_COOKIE_DOMAIN", ".lunastore.app"),
        "Домен session cookie (требует перезагрузки)",
        str,
    ),
    "CSRF_COOKIE_DOMAIN": (
        os.getenv("CSRF_COOKIE_DOMAIN", ".lunastore.app"),
        "Домен CSRF cookie (требует перезагрузки)",
        str,
    ),
    # -- database (require restart) --
    "DB_NAME": (
        os.getenv("DB_NAME", ""),
        "Имя базы данных (требует перезагрузки)",
        str,
    ),
    "DB_USER": (
        os.getenv("DB_USER", "postgres"),
        "Пользователь БД (требует перезагрузки)",
        str,
    ),
    "DB_PASSWORD": (
        os.getenv("DB_PASSWORD", ""),
        "Пароль БД (требует перезагрузки)",
        str,
    ),
    "DB_HOST": (
        os.getenv("DB_HOST", "db"),
        "Хост БД (требует перезагрузки)",
        str,
    ),
    "DB_PORT": (
        os.getenv("DB_PORT", "5432"),
        "Порт БД (требует перезагрузки)",
        str,
    ),
    # -- openid (require restart) --
    "OIDC_CLIENT_ID": (
        os.getenv("OIDC_CLIENT_ID", ""),
        "OpenID Client ID (требует перезагрузки)",
        str,
    ),
    "OIDC_CLIENT_SECRET": (
        os.getenv("OIDC_CLIENT_SECRET", ""),
        "OpenID Client Secret (требует перезагрузки)",
        str,
    ),
    "OIDC_ENDPOINT": (
        os.getenv("OIDC_ENDPOINT", ""),
        "OpenID Authorization Endpoint (требует перезагрузки)",
        str,
    ),
    "OIDC_TOKEN_ENDPOINT": (
        os.getenv("OIDC_TOKEN_ENDPOINT", ""),
        "OpenID Token Endpoint (требует перезагрузки)",
        str,
    ),
    "OIDC_USER_ENDPOINT": (
        os.getenv("OIDC_USER_ENDPOINT", ""),
        "OpenID User Endpoint (требует перезагрузки)",
        str,
    ),
    "LOGIN_REDIRECT_URL": (
        os.getenv("LOGIN_REDIRECT_URL", "/index.php"),
        "URL редиректа после логина (требует перезагрузки)",
        str,
    ),
    "LOGOUT_REDIRECT_URL": (
        os.getenv("LOGOUT_REDIRECT_URL", "/login.php"),
        "URL редиректа после выхода (требует перезагрузки)",
        str,
    ),
    "OIDC_SIGN_ALGO": (
        os.getenv("OIDC_SIGN_ALGO", "RS256"),
        "OpenID алгоритм подписи (требует перезагрузки)",
        str,
    ),
    "OIDC_JWKS_ENDPOINT": (
        os.getenv("OIDC_JWKS_ENDPOINT", ""),
        "OpenID JWKS Endpoint (требует перезагрузки)",
        str,
    ),
    # -- media --
    "EXTERNAL_MEDIA_URL": (
        os.getenv("EXTERNAL_MEDIA_URL", "/media/"),
        "Внешний URL для медиа (требует перезагрузки)",
        str,
    ),
    # -- lunaspire --
    "LUNASPIRE_SECRET_KEY": (
        os.getenv("LUNASPIRE_SECRET_KEY", ""),
        "Секретный ключ LunaSpire (требует перезагрузки)",
        str,
    ),
    "LUNASPIRE_URL": (
        os.getenv("LUNASPIRE_URL", "spire.lunastore.app"),
        "URL LunaSpire (требует перезагрузки)",
        str,
    ),
    "LUNASPIRE_URL_WITHOUT_PROTO": (
        os.getenv("LUNASPIRE_URL_WITHOUT_PROTO", "spire.lunastore.app"),
        "URL LunaSpire без протокола (требует перезагрузки)",
        str,
    ),
    "API_URL": (
        os.getenv("API_URL", "api.lunastore.app"),
        "URL API (требует перезагрузки)",
        str,
    ),
    # -- bcrypt --
    "BCRYPT_ROUNDS": (
        int(os.getenv("BCRYPT_ROUNDS", "12")),
        "Кол-во раундов bcrypt",
        int,
    ),
    # -- registration --
    "REGISTRATION_IS_ENABLED": (
        os.getenv("REGISTRATION_IS_ENABLED", "True") == "True",
        "Включить/выключить регистрацию пользователей",
        bool,
    ),
    "DEVELOPER_REGISTRATION_IS_ENABLED": (
        os.getenv("DEVELOPER_REGISTRATION_IS_ENABLED", "True") == "True",
        "Включить/выключить заявки на статус разработчика",
        bool,
    ),
    # -- invites --
    "INVITES_ON_REGISTER": (
        os.getenv("INVITES_ON_REGISTER", "False") == "True",
        "Регистрация только по инвайтам",
        bool,
    ),
    "MAX_INVITE_USES_COUNT": (
        int(os.getenv("MAX_INVITE_USES_COUNT", "3")),
        "Макс. кол-во использований инвайта за период",
        int,
    ),
    "MAX_INVITE_DAYS_LIMIT": (
        int(os.getenv("MAX_INVITE_DAYS_LIMIT", "7")),
        "Период ограничения инвайтов (дней)",
        int,
    ),
    # -- content --
    "ENABLE_DRM": (
        os.getenv("ENABLE_DRM", "False") == "True",
        "Включить DRM-защиту",
        bool,
    ),
    "MOTD_LIST": (
        os.getenv("MOTD_LIST", "Windows XP Professional"),
        "Список MOTD для шапки сайта (через ;)",
        "textarea",
    ),
    "SCREENSHOT_COUNT": (
        int(os.getenv("SCREENSHOT_COUNT", "3")),
        "Кол-во скриншотов на приложение",
        int,
    ),
    # -- rate limiting --
    "RATE_LIMIT_ENABLED": (
        os.getenv("RATE_LIMIT_ENABLED", "False") == "True",
        "Включить глобальный rate-limit",
        bool,
    ),
    "RATE_LIMIT_WINDOW": (
        int(os.getenv("RATE_LIMIT_WINDOW", "50")),
        "Кол-во запросов в окне rate-limit",
        int,
    ),
    "RATE_LIMIT": (
        int(os.getenv("RATE_LIMIT", "35")),
        "Время окна rate-limit (секунды)",
        int,
    ),
    "NOSPAM_ENABLED": (
        os.getenv("NOSPAM_ENABLED", "False") == "True",
        "Включить noSpam слой",
        bool,
    ),
    "NOSPAM_FAIL_MODE": (
        os.getenv("NOSPAM_FAIL_MODE", "allow"),
        "Поведение при ошибке noSpam: allow|deny|log",
        str,
    ),
    "NOSPAM_CACHE_TTL": (
        int(os.getenv("NOSPAM_CACHE_TTL", "300")),
        "TTL кэша правил noSpam (сек)",
        int,
    ),
    "NOSPAM_SHIELD_ENABLED": (
        os.getenv("NOSPAM_SHIELD_ENABLED", "True") == "True",
        "Включить anti-raider shield mode",
        bool,
    ),
    "NOSPAM_SHIELD_REG_PER_MIN": (
        int(os.getenv("NOSPAM_SHIELD_REG_PER_MIN", "20")),
        "Порог shield: действий с одного IP в минуту",
        int,
    ),
    "NOSPAM_SHIELD_DOMAIN_PER_MIN": (
        int(os.getenv("NOSPAM_SHIELD_DOMAIN_PER_MIN", "30")),
        "Порог shield: действий по домену email в минуту",
        int,
    ),
    "NOSPAM_SHIELD_UA_PER_MIN": (
        int(os.getenv("NOSPAM_SHIELD_UA_PER_MIN", "40")),
        "Порог shield: повторяемость user-agent в минуту",
        int,
    ),
    "NOSPAM_SHIELD_BLOCK_MINUTES": (
        int(os.getenv("NOSPAM_SHIELD_BLOCK_MINUTES", "15")),
        "Длительность shield-блокировки (мин)",
        int,
    ),
    "API_THROTTLE_ENABLED": (
        os.getenv("API_THROTTLE_ENABLED", "True") == "True",
        "Включить DRF throttle для API",
        bool,
    ),
    "API_THROTTLE_ANON_RATE": (
        os.getenv("API_THROTTLE_ANON_RATE", "1000/hour"),
        "Лимит анонимных API-запросов (формат: 1000/hour)",
        str,
    ),
    "API_THROTTLE_USER_RATE": (
        os.getenv("API_THROTTLE_USER_RATE", "5000/hour"),
        "Лимит авторизованных API-запросов (формат: 5000/hour)",
        str,
    ),
    # -- gdpr --
    "RETENTION_ACTIVITY_LOG_DAYS": (
        int(os.getenv("RETENTION_ACTIVITY_LOG_DAYS", "0")),
        "Хранение лога активности (дней, 0 = бессрочно)",
        int,
    ),
    # -- telegram logger --
    "TELEGRAM_LOGGER_ENABLED": (
        os.getenv("TELEGRAM_LOGGER_ENABLED", "False") == "True",
        "Включить Telegram-логгер (требует перезагрузки)",
        bool,
    ),
    "TELEGRAM_BOT_TOKEN": (
        os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "Токен Telegram-бота (требует перезагрузки)",
        str,
    ),
    "TELEGRAM_LOG_CHAT_ID": (
        os.getenv("TELEGRAM_LOG_CHAT_ID", ""),
        "Chat ID для логов (требует перезагрузки)",
        str,
    ),
    "LOG_MODERATOR_LOGINS": (
        os.getenv("LOG_MODERATOR_LOGINS", "True") == "True",
        "Логировать вход модераторов/админов в систему",
        bool,
    ),
    "TELEGRAM_NOTIFY_MODERATOR_LOGINS": (
        os.getenv("TELEGRAM_NOTIFY_MODERATOR_LOGINS", "False") == "True",
        "Отправлять уведомления о входах в Telegram",
        bool,
    ),
    "TELEGRAM_LOG_TOPIC_ID": (
        os.getenv("TELEGRAM_LOG_TOPIC_ID", ""),
        "Topic ID для логов (требует перезагрузки)",
        str,
    ),
    # -- sentry/glitchtip --
    "SENTRY_ENABLED": (
        os.getenv("SENTRY_ENABLED", "False") == "True",
        "Включить Sentry/GlitchTip (требует перезагрузки)",
        bool,
    ),
    "SENTRY_DSN": (
        os.getenv("SENTRY_DSN", ""),
        "Sentry DSN (требует перезагрузки)",
        str,
    ),
    "SENTRY_TRACES_SAMPLE_RATE": (
        float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
        "Sentry traces sample rate (требует перезагрузки)",
        float,
    ),
    "SENTRY_PROFILES_SAMPLE_RATE": (
        float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        "Sentry profiles sample rate (требует перезагрузки)",
        float,
    ),
    "SENTRY_ENVIRONMENT": (
        os.getenv("SENTRY_ENVIRONMENT", "production"),
        "Sentry environment tag (требует перезагрузки)",
        str,
    ),
    # -- clickhouse analytics --
    "ANALYTICS_ENABLED": (
        os.getenv("ANALYTICS_ENABLED", "False") == "True",
        "Включить ClickHouse-аналитику",
        bool,
    ),
    # -- email (require restart) --
    "EMAIL_HOST": (
        os.getenv("EMAIL_HOST", ""),
        "SMTP хост (требует перезагрузки)",
        str,
    ),
    "EMAIL_PORT": (
        int(os.getenv("EMAIL_PORT", "587")),
        "SMTP порт (требует перезагрузки)",
        int,
    ),
    "EMAIL_USE_TLS": (
        os.getenv("EMAIL_USE_TLS", "True") == "True",
        "Использовать TLS для SMTP (требует перезагрузки)",
        bool,
    ),
    "EMAIL_USE_SSL": (
        os.getenv("EMAIL_USE_SSL", "False") == "True",
        "Использовать SSL для SMTP (требует перезагрузки)",
        bool,
    ),
    "EMAIL_HOST_USER": (
        os.getenv("EMAIL_HOST_USER", ""),
        "SMTP пользователь (требует перезагрузки)",
        str,
    ),
    "EMAIL_HOST_PASSWORD": (
        os.getenv("EMAIL_HOST_PASSWORD", ""),
        "SMTP пароль (требует перезагрузки)",
        str,
    ),
    "DEFAULT_FROM_EMAIL": (
        os.getenv("DEFAULT_FROM_EMAIL", ""),
        "Email отправителя по умолчанию (требует перезагрузки)",
        str,
    ),
    "GEO_DOMAIN_PROXY_ENABLED": (
        os.getenv("GEO_DOMAIN_PROXY_ENABLED", "True") == "True",
        "Включить переопределения доменов (Geo Proxy)",
        bool,
    ),
    "GEO_DOMAIN_OVERRIDES": (
        '{\n  "RU": {\n    "BASE_URL": "ru.lunastore.app",\n    "API_URL": "api.ru.lunastore.app",\n    "SPIRE_URL": "spire.ru.lunastore.app"\n  }\n}',
        "Переопределения доменов по странам (JSON)",
        "textarea",
    ),
    "ENABLE_DISTRIBUTION_PROXY": (
        os.getenv("ENABLE_DISTRIBUTION_PROXY", "True") == "True",
        "Проксировать внешние ссылки скачивания (дистрибуции) через Nginx (X-Accel-Redirect)",
        bool,
    ),
    "ALLOW_MODERATOR_LOGIN_AS_USER": (
        os.getenv("ALLOW_MODERATOR_LOGIN_AS_USER", "False") == "True",
        "Разрешить модераторам входить от имени других пользователей",
        bool,
    ),
}

CONSTANCE_CONFIG_FIELDSETS = {
    "Регистрация": {
        "fields": [
            "REGISTRATION_IS_ENABLED",
            "DEVELOPER_REGISTRATION_IS_ENABLED",
        ],
        "collapse": True,
    },
    "Инвайты": {
        "fields": [
            "INVITES_ON_REGISTER",
            "MAX_INVITE_USES_COUNT",
            "MAX_INVITE_DAYS_LIMIT",
        ],
        "collapse": True,
    },
    "Контент и внешний вид": {
        "fields": ["MOTD_LIST", "SCREENSHOT_COUNT", "ENABLE_DRM", "ENABLE_DISTRIBUTION_PROXY"],
        "collapse": True,
    },
    "Rate Limiting": {
        "fields": [
            "RATE_LIMIT_ENABLED",
            "RATE_LIMIT_WINDOW",
            "RATE_LIMIT",
            "API_THROTTLE_ENABLED",
            "API_THROTTLE_ANON_RATE",
            "API_THROTTLE_USER_RATE",
        ],
        "collapse": True,
    },
    "NoSpam и anti-raider": {
        "fields": [
            "NOSPAM_ENABLED",
            "NOSPAM_FAIL_MODE",
            "NOSPAM_CACHE_TTL",
            "NOSPAM_SHIELD_ENABLED",
            "NOSPAM_SHIELD_REG_PER_MIN",
            "NOSPAM_SHIELD_DOMAIN_PER_MIN",
            "NOSPAM_SHIELD_UA_PER_MIN",
            "NOSPAM_SHIELD_BLOCK_MINUTES",
        ],
        "collapse": True,
    },
    "GDPR и безопасность": {
        "fields": ["RETENTION_ACTIVITY_LOG_DAYS", "BCRYPT_ROUNDS", "ALLOW_MODERATOR_LOGIN_AS_USER"],
        "collapse": True,
    },
    "LunaStore Core (требует перезагрузки)": {
        "fields": [
            "VERSION",
            "DEBUG",
            "SECRET_KEY",
            "ADMIN_URL",
            "ADMIN_EMAIL",
        ],
        "collapse": True,
    },
    "Хосты и домены (требует перезагрузки)": {
        "fields": [
            "ALLOWED_HOSTS",
            "CORS_ALLOWED_ORIGINS",
            "CSRF_TRUSTED_ORIGINS",
            "SESSION_COOKIE_DOMAIN",
            "CSRF_COOKIE_DOMAIN",
        ],
        "collapse": True,
    },
    "База данных (требует перезагрузки)": {
        "fields": ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"],
        "collapse": True,
    },
    "OpenID (требует перезагрузки)": {
        "fields": [
            "OIDC_CLIENT_ID",
            "OIDC_CLIENT_SECRET",
            "OIDC_ENDPOINT",
            "OIDC_TOKEN_ENDPOINT",
            "OIDC_USER_ENDPOINT",
            "LOGIN_REDIRECT_URL",
            "LOGOUT_REDIRECT_URL",
            "OIDC_SIGN_ALGO",
            "OIDC_JWKS_ENDPOINT",
        ],
        "collapse": True,
    },
    "Медиа (требует перезагрузки)": {
        "fields": ["EXTERNAL_MEDIA_URL"],
        "collapse": True,
    },
    "LunaSpire (требует перезагрузки)": {
        "fields": [
            "LUNASPIRE_SECRET_KEY",
            "LUNASPIRE_URL",
            "LUNASPIRE_URL_WITHOUT_PROTO",
            "API_URL",
        ],
        "collapse": True,
    },
    "Telegram-логгер (требует перезагрузки)": {
        "fields": [
            "TELEGRAM_LOGGER_ENABLED",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_LOG_CHAT_ID",
            "TELEGRAM_LOG_TOPIC_ID",
            "LOG_MODERATOR_LOGINS",
            "TELEGRAM_NOTIFY_MODERATOR_LOGINS",
        ],
        "collapse": True,
    },
    "Sentry / GlitchTip (требует перезагрузки)": {
        "fields": [
            "SENTRY_ENABLED",
            "SENTRY_DSN",
            "SENTRY_TRACES_SAMPLE_RATE",
            "SENTRY_PROFILES_SAMPLE_RATE",
            "SENTRY_ENVIRONMENT",
        ],
        "collapse": True,
    },
    "Analytics / ClickHouse": {
        "fields": [
            "ANALYTICS_ENABLED",
        ],
        "collapse": True,
    },
    "Email и SMTP (требует перезагрузки)": {
        "fields": [
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_USE_TLS",
            "EMAIL_USE_SSL",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "DEFAULT_FROM_EMAIL",
        ],
        "collapse": True,
    },
    "Geo Реверс-прокси": {
        "fields": ["GEO_DOMAIN_PROXY_ENABLED", "GEO_DOMAIN_OVERRIDES"],
        "collapse": True,
    },
}

# media path

MEDIA_URL = os.getenv("EXTERNAL_MEDIA_URL", "http://192.168.1.10:9088/media/")
MEDIA_ROOT = BASE_DIR / "media"

# openid AP configuration

AUTHENTICATION_BACKENDS = [
    "apps.user.auth.OIDCModel",
    "django.contrib.auth.backends.ModelBackend",
]

OIDC_RP_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv("OIDC_ENDPOINT", "")
OIDC_OP_TOKEN_ENDPOINT = os.getenv("OIDC_TOKEN_ENDPOINT", "")
OIDC_OP_USER_ENDPOINT = os.getenv("OIDC_USER_ENDPOINT", "")
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL", "/")
LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL", "/login.php")
OIDC_OP_JWKS_ENDPOINT = os.getenv("OIDC_JWKS_ENDPOINT", "")
# mozilla-django-oidc calls .startswith on this in __init__; never leave as None
OIDC_RP_SIGN_ALGO = os.getenv("OIDC_SIGN_ALGO", "RS256")


def custom_environment_callback(request):
    return ["Production", "info"] if not DEBUG else ["Development", "success"]


def _admin_url_name_active(request, url_names: tuple[str, ...]) -> bool:
    match = getattr(request, "resolver_match", None)
    if match is None:
        return False
    return match.url_name in url_names


def nospam_rules_sidebar_active(request) -> bool:
    return _admin_url_name_active(
        request,
        (
            "user_nospamrule_changelist",
            "user_nospamrule_add",
            "user_nospamrule_change",
            "user_nospamrule_delete",
            "user_nospamrule_history",
        ),
    )


def nospam_mass_scan_sidebar_active(request) -> bool:
    return _admin_url_name_active(request, ("admin_nospam_mass_scan",))


def nospam_events_sidebar_active(request) -> bool:
    return _admin_url_name_active(
        request,
        (
            "user_nospamevent_changelist",
            "user_nospamevent_change",
            "user_nospamevent_history",
        ),
    )


# customize unfold theme
UNFOLD = {"SITE_TITLE": "Панель LunaStore",
          "SITE_HEADER": "LunaStore",
          "SITE_SUBHEADER": "админ-панель",
          "SITE_URL": "/",
          "SITE_ICON": {"light": lambda request: static("img/logo.png"),
                        "dark": lambda request: static("img/logo.png"),
                        },
          "SITE_SYMBOL": "speed",
          "SITE_FAVICONS": [{"rel": "icon",
                             "sizes": "32x32",
                             "type": "image/svg+xml",
                             "href": lambda request: static("favicon.ico"),
                             },
                            ],
          "LOGIN": {"image": lambda request: static("img/ap_bg_lunastore.png"),
                    },
          "SHOW_HISTORY": True,
          "BORDER_RADIUS": "8px",
          "DASHBOARD_CALLBACK": "apps.core.dashboard.callback",
          "SHOW_VIEW_ON_SITE": True,
          "SHOW_BACK_BUTTON": False,
          "COLORS": {"base": {"50": "#f8fafc",
                              "100": "#f1f5f9",
                              "200": "#e2e8f0",
                              "300": "#cbd5e1",
                              "400": "#94a3b8",
                              "500": "#64748b",
                              "600": "#475569",
                              "700": "#334155",
                              "800": "#1e293b",
                              "900": "#0f172a",
                              "950": "#020617",
                              },
                     "primary": {"50": "#eef2ff",
                                 "100": "#e0e7ff",
                                 "200": "#c7d2fe",
                                 "300": "#a5b4fc",
                                 "400": "#818cf8",
                                 "500": "#6366f1",
                                 "600": "#4f46e5",
                                 "700": "#4338ca",
                                 "800": "#3730a3",
                                 "900": "#312e81",
                                 "950": "#1e1b4b",
                                 },
                     "font": {"subtle-light": "var(--color-base-500)",
                              "subtle-dark": "var(--color-base-400)",
                              "default-light": "var(--color-base-600)",
                              "default-dark": "var(--color-base-300)",
                              "important-light": "var(--color-base-900)",
                              "important-dark": "var(--color-base-100)",
                              },
                     },
          "STYLES": [lambda request: static("css/admin_custom.css"),
                     ],
          "ENVIRONMENT": "lunastore.settings.custom_environment_callback",
          "EXTENSIONS": {"modeltranslation": {"flags": {"en": " ( 🇺🇸 )",
                                                        "ru": " ( 🇷🇺 )",
                                                        "be": " ( 🇧🇾 )",
                                                        "uk": " ( 🇺🇦 )",
                                                        },
                                              },
                         },
          "TABS": [{"models": ["terms.legaldocument",
                               "core.banner",
                               "user.user",
                               "user.userban",
                               "auth.group",
                               "user.blacklistedusername",
                               "user.invitetoken",
                               ],
                    "items": [{"title": "Документы и Баннеры",
                               "link": reverse_lazy("admin:terms_legaldocument_changelist"),
                               "icon": "description",
                               },
                              {"title": "Аккаунты",
                               "link": reverse_lazy("admin:user_user_changelist"),
                               "icon": "people",
                               },
                              ],
                    },
                   {"models": ["marketplace.application",
                               "marketplace.category",
                               "marketplace.distribution",
                               "marketplace.badge",
                               "marketplace.appreportrequests",
                               "marketplace.problemreportrequests",
                               "marketplace.appeditrequests",
                               "user.devrequestsmodel",
                               ],
                    "items": [{"title": "Приложения",
                               "link": reverse_lazy("admin:marketplace_application_changelist"),
                               "icon": "apps",
                               },
                              {"title": "Заявки",
                               "link": reverse_lazy("admin:marketplace_appeditrequests_changelist"),
                               "icon": "assignment",
                               },
                              ],
                    },
                   ],
          "SIDEBAR": {"show_search": False,
                      "show_all_applications": False,
                      "navigation": [{"title": "Внутренняя часть",
                                      "separator": False,
                                      "items": [{"title": "Юридические документы",
                                                 "icon": "description",
                                                 "link": reverse_lazy("admin:terms_legaldocument_changelist"),
                                                 "permission": lambda request: request.user.has_perm("terms.view_legaldocument"),
                                                 },
                                                {"title": "Баннера",
                                                 "icon": "image",
                                                 "link": reverse_lazy("admin:core_banner_changelist"),
                                                 "permission": lambda request: request.user.has_perm("core.view_banner"),
                                                 }],
                                      },
                                     {"title": "Аккаунт",
                                      "separator": True,
                                      "items": [{"title": "Пользователи",
                                                 "icon": "group",
                                                 "link": reverse_lazy("admin:user_user_changelist"),
                                                 "permission": lambda request: request.user.has_perm("user.view_user"),
                                                 },
                                                {"title": "Блокировки",
                                                 "icon": "gavel",
                                                 "link": reverse_lazy("admin:user_userban_changelist"),
                                                 "permission": lambda request: request.user.has_perm("user.view_userban"),
                                                 },
                                                {"title": "Группы",
                                                 "icon": "group",
                                                 "link": reverse_lazy("admin:auth_group_changelist"),
                                                 "permission": lambda request: request.user.has_perm("auth.view_group"),
                                                 },
                                                {"title": "Черный список никнеймов",
                                                 "icon": "person_cancel",
                                                 "link": reverse_lazy("admin:user_blacklistedusername_changelist"),
                                                 "permission": lambda request: request.user.has_perm("user.view_blacklistedusername"),
                                                 },
                                                {"title": "Инвайт-токены",
                                                 "icon": "redeem",
                                                 "link": reverse_lazy("admin:user_invitetoken_changelist"),
                                                 "permission": lambda request: request.user.has_perm("user.view_invitetoken"),
                                                 }],
                                      },
                                     {"title": "noSpam",
                                      "separator": True,
                                      "items": [{"title": "Правила noSpam",
                                                 "icon": "shield",
                                                 "link": reverse_lazy("admin:user_nospamrule_changelist"),
                                                 "active": nospam_rules_sidebar_active,
                                                 "permission": lambda request: request.user.has_perm("user.view_nospamrule"),
                                                 },
                                                {"title": "Массовая проверка",
                                                 "icon": "manage_search",
                                                 "link": reverse_lazy("admin_nospam_mass_scan"),
                                                 "active": nospam_mass_scan_sidebar_active,
                                                 "permission": lambda request: request.user.has_perm("user.view_nospamrule"),
                                                 },
                                                {"title": "События noSpam",
                                                 "icon": "history",
                                                 "link": reverse_lazy("admin:user_nospamevent_changelist"),
                                                 "active": nospam_events_sidebar_active,
                                                 "permission": lambda request: request.user.has_perm("user.view_nospamevent"),
                                                 }],
                                      },
                                     {"title": "Приложения",
                                      "separator": True,
                                      "items": [{"title": "Приложения",
                                                 "icon": "apps",
                                                 "link": reverse_lazy("admin:marketplace_application_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_application"),
                                                 },
                                                {"title": "Категории",
                                                 "icon": "category",
                                                 "link": reverse_lazy("admin:marketplace_category_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_category"),
                                                 },
                                                {"title": "Бейджики",
                                                 "icon": "local_police",
                                                 "link": reverse_lazy("admin:marketplace_badge_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_badge"),
                                                 },
                                                {"title": "Дистрибуции",
                                                 "icon": "app_registration",
                                                 "link": reverse_lazy("admin:marketplace_distribution_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_distribution"),
                                                 },
                                                {"title": "Жалобы на приложения",
                                                 "icon": "report",
                                                 "link": reverse_lazy("admin:marketplace_appreportrequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_appreportrequests"),
                                                 },
                                                {"title": "Жалобы на проблемы",
                                                 "icon": "flag",
                                                 "link": reverse_lazy("admin:marketplace_problemreportrequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_problemreportrequests"),
                                                 },
                                                ],
                                      },
                                     {"title": "Заявки",
                                      "separator": True,
                                      "items": [{"title": "Создание приложения",
                                                 "icon": "apps",
                                                 "link": reverse_lazy("admin:marketplace_appcreaterequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_appcreaterequests"),
                                                 },
                                                {"title": "Изменение приложения",
                                                 "icon": "edit",
                                                 "link": reverse_lazy("admin:marketplace_appeditrequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_appeditrequests"),
                                                 },
                                                {"title": "Статус разработчика",
                                                 "icon": "computer",
                                                 "link": reverse_lazy("admin:user_devrequestsmodel_changelist"),
                                                 "permission": lambda request: request.user.has_perm("user.view_devrequestsmodel"),
                                                 },
                                                {"title": "Создание дистрибуции",
                                                 "icon": "publish",
                                                 "link": reverse_lazy("admin:marketplace_distributioncreaterequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_distributioncreaterequests"),
                                                 },
                                                {"title": "Редактирование дистрибуции",
                                                 "icon": "edit",
                                                 "link": reverse_lazy("admin:marketplace_distributioneditrequests_changelist"),
                                                 "permission": lambda request: request.user.has_perm("marketplace.view_distributioneditrequests"),
                                                 },
                                                ],
                                      },
                                     {"title": "Управление",
                                      "separator": True,
                                      "items": [{"title": "Настройки сайта",
                                                 "icon": "settings",
                                                 "link": reverse_lazy("admin:constance_config_changelist"),
                                                 "permission": lambda request: request.user.has_perm("constance.change_config"),
                                                 },
                                                {"title": "Рассылка уведомлений",
                                                 "icon": "breaking_news",
                                                 "link": reverse_lazy("broadcast"),
                                                 "permission": lambda request: request.user.is_superuser,
                                                 },
                                                {"title": "Логи",
                                                 "icon": "history",
                                                 "link": reverse_lazy("admin:admin_logentry_changelist"),
                                                 "permission": lambda request: request.user.has_perm("admin.view_logentry"),
                                                 }],
                                      }],
                      },
          }

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'django_user_agents.middleware.UserAgentMiddleware',
    "apps.user.middleware.UserSessionMiddleware",
    "apps.core.middleware.GeoDomainMiddleware",
    *([] if not RATE_LIMIT_ENABLED else ["apps.core.middleware.RateLimitMiddleware"]),
]

ROOT_URLCONF = os.environ.get("DJANGO_ROOT_URLCONF", "lunastore.urls")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "apps.core.context_processors.motd_processor",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.random_banner",
                "apps.core.context_processors.drm_settings",
                "apps.core.context_processors.geo_domains_processor",
                "apps.core.context_processors.notification_context",
            ],
        },
    },
]

WSGI_APPLICATION = "lunastore.wsgi.application"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# bcrypt2a hash in auth model in django
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# default number of rounds in bcrypt ¯\_(ツ)_/¯; if you want, you can
# change this number
BCRYPT_ROUNDS = os.getenv("BCRYPT_ROUNDS", 12)

# name of custom user model; please do not change this unless you know
# what you are doing
AUTH_USER_MODEL = "user.User"

# business settings moved to django-constance (CONSTANCE_CONFIG)
# access them at runtime via: from constance import config; config.SETTING_NAME

WHITENOISE_MANIFEST_STRICT = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "debug.log",
            "maxBytes": 15 * 1024 * 1024,  # 15 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "user": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "marketplace": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "analytics": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

LANGUAGE_CODE = "ru"

LANGUAGES = [
    ("ru", "рус"),
    ("en", "eng"),
    ("uk", "укр"),
    ("be", "бел"),
    ("kk", "қаз"),
]

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/staticfiles/"
STATICFILES_DIRS = [BASE_DIR / "staticfiles"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}

if "test" in sys.argv:
    STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    }
    CONSTANCE_BACKEND = "constance.backends.memory.MemoryBackend"

PASSWORD_RESET_TIMEOUT = 3600
