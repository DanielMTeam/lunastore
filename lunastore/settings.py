import os
from pathlib import Path

from django.templatetags.static import static
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)

# PLEASE, do not change this, if you don't understand what you do
VERSION = os.getenv("VERSION", "1.7.0")

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

DEBUG = os.getenv("DEBUG", "False") == "True"

LUNASPIRE_SECRET_KEY = os.getenv("LUNASPIRE_SECRET_KEY")
LUNASPIRE_URL = os.getenv("LUNASPIRE_URL")
API_URL = os.getenv("API_URL", "http://localhost:7088")

ADMIN_URL = os.getenv("ADMIN_URL", "admin")

CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN", ".lunastore.app")
CSRF_COOKIE_DOMAIN = os.getenv("CSRF_COOKIE_DOMAIN", ".lunastore.app")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(";")
    SESSION_COOKIE_SAMESITE = "Lax"
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
    "django.contrib.auth",
    "mozilla_django_oidc",  # openid
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.marketplace.apps.MarketplaceConfig",
    "apps.user.apps.UserConfig",
    "apps.core.apps.CoreConfig",
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
    "django.contrib.admin",
    "django_cleanup.apps.CleanupConfig",
    "django.contrib.postgres",
    "rest_framework",
    "apps.api.apps.APIConfig",
    "drf_spectacular",
    "corsheaders",
    "django_extensions",
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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache",
    }
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

# customize unfold theme
UNFOLD = {
    "SITE_TITLE": "Панель LunaStore",
    "SITE_HEADER": "LunaStore",
    "SITE_SUBHEADER": "панель для модерации сайта",
    "SITE_DROPDOWN": [
        {"icon": "home", "title": "LunaStore", "link": "https://lunastore.app"},
    ],
    "SITE_URL": "/",
    "SITE_LOGO": {
        "light": lambda request: static("img/logo.png"),
        "dark": lambda request: static("img/logo.png"),
    },
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
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .002 252.0)",
            "100": "oklch(96.7% .003 252.0)",
            "200": "oklch(92.8% .006 252.0)",
            "300": "oklch(87.2% .01 252.0)",
            "400": "oklch(70.7% .022 252.0)",
            "500": "oklch(55.1% .027 252.0)",
            "600": "oklch(44.6% .03 252.0)",
            "700": "oklch(37.3% .034 252.0)",
            "800": "oklch(27.8% .033 252.0)",
            "900": "oklch(21% .034 252.0)",
            "950": "oklch(13% .028 252.0)",
        },
        "primary": {
            "50": "oklch(97.1% .014 252.0)",
            "100": "oklch(94.2% .033 252.0)",
            "200": "oklch(89.5% .063 252.0)",
            "300": "oklch(81.8% .119 252.0)",
            "400": "oklch(70.1% .165 252.0)",
            "500": "oklch(61.2% .195 252.0)",
            "600": "oklch(53.5% .205 252.0)",
            "700": "oklch(46.8% .190 252.0)",
            "800": "oklch(40.2% .160 252.0)",
            "900": "oklch(34.5% .130 252.0)",
            "950": "oklch(26.0% .110 252.0)",
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
]

ROOT_URLCONF = os.environ.get("DJANGO_ROOT_URLCONF", "lunastore.urls")
print(ROOT_URLCONF)

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
                "apps.core.context_processors.random_banner",
                "apps.core.context_processors.drm_settings",
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

# if REGISTRATION_IS_ENABLED = True, we will render register.html on '/register.php' path; if False, we will render register_on.html
REGISTRATION_IS_ENABLED = os.getenv("REGISTRATION_IS_ENABLED", True)

# if DEVELOPER_REGISTRATION_IS_ENABLED = True, we will allow users to send dev status requests
DEVELOPER_REGISTRATION_IS_ENABLED = os.getenv("DEVELOPER_REGISTRATION_IS_ENABLED", True)

# User Activity Log (include IPs) retention period in days (because storage limitation gdpr; we must store data for the shortest time possible)
RETENTION_ACTIVITY_LOG_DAYS = os.getenv("RETENTION_ACTIVITY_LOG_DAYS", 0)

# number of screenshots allowed per application
SCREENSHOT_COUNT = 3

INVITES_ON_REGISTER = os.getenv("INVITES_ON_REGISTER", False)
MAX_INVITE_USES_COUNT = os.getenv("MAX_INVITE_USES_COUNT", 3)
MAX_INVITE_DAYS_LIMIT = os.getenv("MAX_INVITE_DAYS_LIMIT", 7)

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
    },
}

LANGUAGE_CODE = "ru"

LANGUAGES = [("ru", "Russian")]

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/staticfiles/"
STATICFILES_DIRS = [BASE_DIR / "staticfiles"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
