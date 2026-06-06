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

# sentry/glitchtip error tracking
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "False") == "True"
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production")

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
VERSION = os.getenv("VERSION", "2.1")

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

GEOIP_PATH = BASE_DIR / 'apps' / 'core' / 'geolocation'

ADMIN_URL = os.getenv("ADMIN_URL", "http://127.0.0.1:8000")

LOGIN_URL = "login.php"

# global rate limit settings
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "False") == "True"
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "50"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "35"))

# django-smart-ratelimit (ratelimit for functions)
RATELIMIT_BACKEND = 'redis'
RATELIMIT_REDIS = {
    'host': 'redis',
    'port': 6379,
    'db': 1,
}

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

LOGIN_REDIRECT_URL = "/index.php"

LOGOUT_REDIRECT_URL = "/login.php"

DEBUG = os.getenv("DEBUG", "False") == "True"

TELEGRAM_LOGGER_ENABLED = os.getenv("TELEGRAM_LOGGER_ENABLED", "False") == "True"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_LOG_CHAT_ID = os.getenv("TELEGRAM_LOG_CHAT_ID", "")
TELEGRAM_LOG_TOPIC_ID = os.getenv("TELEGRAM_LOG_TOPIC_ID", "")

LUNASPIRE_SECRET_KEY = os.getenv("LUNASPIRE_SECRET_KEY")
LUNASPIRE_URL = os.getenv("LUNASPIRE_URL", "spire.lunastore.app")
API_URL = os.getenv("API_URL", "api.lunastore.app")

ADMIN_URL = os.getenv("ADMIN_URL", "admin")

CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", ".lunastore.app")
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", ".lunastore.app")

LUNASPIRE_URL_WITHOUT_PROTO = os.getenv(
    "LUNASPIRE_URL_WITHOUT_PROTO", "spire.lunastore.app"
)

if not DEBUG:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(";")
    SESSION_COOKIE_SAMESITE = None
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(";")

SECRET_KEY = os.getenv("SECRET_KEY")

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(";") if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    c.strip() for c in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(";") if c.strip()
]

# MOTD List of site (you can see that in the header)
MOTD_LIST = [
    msg.strip() for msg in os.getenv("MOTD_LIST", "").split(";") if msg.strip()
]

STATIC_ROOT = BASE_DIR / "static"

ENABLE_DRM = os.getenv("ENABLE_DRM", "False")

# Application definition

INSTALLED_APPS = [
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
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.api.handlers.luna_exception_handler",
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        # 'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
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
            "LOCATION": "redis://redis:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }

from unfold.contrib.constance.settings import UNFOLD_CONSTANCE_ADDITIONAL_FIELDS

# django-constance configuration
# backend: Redis (same instance as cache)
CONSTANCE_BACKEND = "constance.backends.redisd.RedisBackend"
CONSTANCE_REDIS_CONNECTION = "redis://redis:6379/1"

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
        "fields": ["MOTD_LIST", "SCREENSHOT_COUNT", "ENABLE_DRM"],
        "collapse": True,
    },
    "Rate Limiting": {
        "fields": [
            "RATE_LIMIT_ENABLED",
            "RATE_LIMIT_WINDOW",
            "RATE_LIMIT",
        ],
        "collapse": True,
    },
    "GDPR и безопасность": {
        "fields": ["RETENTION_ACTIVITY_LOG_DAYS", "BCRYPT_ROUNDS"],
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
}

# media path

MEDIA_URL = os.getenv("EXTERNAL_MEDIA_URL", "http://192.168.1.10:9088/media/")
MEDIA_ROOT = BASE_DIR / "media"

# openid AP configuration

AUTHENTICATION_BACKENDS = [
    "apps.user.auth.OIDCModel",
    "django.contrib.auth.backends.ModelBackend",
]

OIDC_RP_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET")
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv("OIDC_ENDPOINT")
OIDC_OP_TOKEN_ENDPOINT = os.getenv("OIDC_TOKEN_ENDPOINT")
OIDC_OP_USER_ENDPOINT = os.getenv("OIDC_USER_ENDPOINT")
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL")
LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL")
OIDC_OP_JWKS_ENDPOINT = os.getenv("OIDC_JWKS_ENDPOINT")
OIDC_RP_SIGN_ALGO = os.getenv("OIDC_SIGN_ALGO")

def custom_environment_callback(request):
    return ["Production", "info"] if not DEBUG else ["Development", "success"]

# customize unfold theme
UNFOLD = {
    "SITE_TITLE": "Панель LunaStore",
    "SITE_HEADER": "LunaStore",
    "SITE_SUBHEADER": "админ-панель",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("img/logo.png"),
        "dark": lambda request: static("img/logo.png"),
    },
    "SITE_SYMBOL": "speed",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/svg+xml",
            "href": lambda request: static("favicon.ico"),
        },
    ],
    "LOGIN": {
        "image": lambda request: static("img/ap_bg_lunastore.png"),
    },
    "SHOW_HISTORY": True,
    "BORDER_RADIUS": "8px",
    "DASHBOARD_CALLBACK": "apps.core.dashboard.callback",
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "COLORS": {
        "base": {
            "50": "#f8fafc",
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
        "primary": {
            "50": "#eef2ff",
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
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "STYLES": [
        lambda request: static("css/admin_custom.css"),
    ],
    "ENVIRONMENT": "lunastore.settings.custom_environment_callback",
    "EXTENSIONS": {
        "modeltranslation": {
            "flags": {
                "en": " ( 🇺🇸 )",
                "ru": " ( 🇷🇺 )",
                "be": " ( 🇧🇾 )",
                "uk": " ( 🇺🇦 )",
            },
        },
    },
    "TABS": [
        {
            "models": [
                "terms.legaldocument",
                "core.banner",
                "user.user",
                "user.userban",
                "auth.group",
                "user.blacklistedusername",
                "user.invitetoken",
            ],
            "items": [
                {
                    "title": "Документы и Баннеры",
                    "link": reverse_lazy("admin:terms_legaldocument_changelist"),
                    "icon": "description",
                },
                {
                    "title": "Аккаунты",
                    "link": reverse_lazy("admin:user_user_changelist"),
                    "icon": "people",
                },
            ],
        },
        {
            "models": [
                "marketplace.application",
                "marketplace.category",
                "marketplace.distribution",
                "marketplace.appreportrequests",
                "marketplace.problemreportrequests",
                "marketplace.appeditrequests",
                "user.devrequestsmodel",
            ],
            "items": [
                {
                    "title": "Приложения",
                    "link": reverse_lazy("admin:marketplace_application_changelist"),
                    "icon": "apps",
                },
                {
                    "title": "Заявки",
                    "link": reverse_lazy("admin:marketplace_appeditrequests_changelist"),
                    "icon": "assignment",
                },
            ],
        },
    ],
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Внутренняя часть",
                "separator": False,
                "items": [
                    {
                        "title": "Юридические документы",
                        "icon": "description",
                        "link": reverse_lazy("admin:terms_legaldocument_changelist"),
                    },
                    {
                        "title": "Баннера",
                        "icon": "image",
                        "link": reverse_lazy("admin:core_banner_changelist"),
                    }
                ],
            },
            {
                "title": "Аккаунт",
                "separator": True,
                "items": [
                    {
                        "title": "Пользователи",
                        "icon": "group",
                        "link": reverse_lazy("admin:user_user_changelist"),
                    },
                    {
                        "title": "Блокировки",
                        "icon": "gavel",
                        "link": reverse_lazy("admin:user_userban_changelist"),
                    },
                    {
                        "title": "Группы",
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": "Черный список никнеймов",
                        "icon": "person_cancel",
                        "link": reverse_lazy("admin:user_blacklistedusername_changelist"),
                    },
                    {
                        "title": "Инвайт-токены",
                        "icon": "redeem",
                        "link": reverse_lazy("admin:user_invitetoken_changelist"),
                    }
                ],
            },
            {
                "title": "Приложения",
                "separator": True,
                "items": [
                    {
                        "title": "Приложения",
                        "icon": "apps",
                        "link": reverse_lazy("admin:marketplace_application_changelist"),
                    },
                    {
                        "title": "Категории",
                        "icon": "category",
                        "link": reverse_lazy("admin:marketplace_category_changelist"),
                    },
                    {
                        "title": "Дистрибуции",
                        "icon": "app_registration",
                        "link": reverse_lazy("admin:marketplace_distribution_changelist"),
                    },
                    {
                        "title": "Жалобы на приложения",
                        "icon": "report",
                        "link": reverse_lazy("admin:marketplace_appreportrequests_changelist"),
                    },
                    {
                        "title": "Жалобы на проблемы",
                        "icon": "flag",
                        "link": reverse_lazy("admin:marketplace_problemreportrequests_changelist"),
                    },

                ],
            },
            {
                "title": "Заявки",
                "separator": True,
                "items": [
                    {
                        "title": "Создание приложения",
                        "icon": "apps",
                        "link": reverse_lazy("admin:marketplace_appcreaterequests_changelist"),
                    },
                    {
                        "title": "Изменение приложения",
                        "icon": "edit",
                        "link": reverse_lazy("admin:marketplace_appeditrequests_changelist"),
                    },
                    {
                        "title": "Статус разработчика",
                        "icon": "computer",
                        "link": reverse_lazy("admin:user_devrequestsmodel_changelist"),
                    },
                    {
                        "title": "Создание дистрибуции",
                        "icon": "publish",
                        "link": reverse_lazy("admin:marketplace_distributioncreaterequests_changelist"),
                    },
                    {
                        "title": "Редактирование дистрибуции",
                        "icon": "edit",
                        "link": reverse_lazy("admin:marketplace_distributioneditrequests_changelist"),
                    },
                ],
            },
            {
                "title": "Управление",
                "separator": True,
                "items": [
                    {
                        "title": "Настройки сайта",
                        "icon": "settings",
                        "link": reverse_lazy("admin:constance_config_changelist"),
                    },
                    {
                        "title": "Рассылка уведомлений",
                        "icon": "breaking_news",
                        "link": reverse_lazy("broadcast"),
                    },
                    {
                        "title": "Логи",
                        "icon": "history",
                        "link": reverse_lazy("admin:admin_logentry_changelist"),
                    }
                ],
            }
        ],
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

BCRYPT_ROUNDS = os.getenv(
    "BCRYPT_ROUNDS", 12
)  # default number of rounds in bcrypt ¯\_(ツ)_/¯; if you want, you can change this number

# name of custom user model; please do not change this unless you know what you are doing
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
            "class": "logging.FileHandler",
            "filename": "debug.log",
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
