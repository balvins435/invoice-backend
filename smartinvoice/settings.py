"""
Django settings for smartinvoice project.
"""
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import environ

# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")


def _clean_origin(value: str) -> str:
    origin = (value or "").strip().strip("<>").strip()
    if origin.endswith("/"):
        origin = origin[:-1]
    return origin


def _is_valid_origin(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _unique(seq):
    seen = set()
    out = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-change-me-in-production",
)
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
render_external_hostname = env("RENDER_EXTERNAL_HOSTNAME", default="")
is_render = bool(render_external_hostname) or env.bool("RENDER", default=False)
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "rest_framework_simplejwt",
    "django_filters",
    "rest_framework_simplejwt.token_blacklist",
    "social_django",
    "drf_yasg",
    "django_extensions",
    "django_celery_results",
    "django_celery_beat",
    "invoice",
    "users",
    "business",
    "expenses",
    "reports",
    "payments",
    "messaging",
    "tax",
    "ai",

]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        *MIDDLEWARE,
    ]
    INTERNAL_IPS = ["127.0.0.1"]

ROOT_URLCONF = "smartinvoice.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "smartinvoice.wsgi.application"

database_url = env("DATABASE_URL", default="")
if database_url:
    DATABASES = {"default": env.db("DATABASE_URL")}
elif is_render:
    # On Render, avoid using localhost DB values from checked-in .env.
    # Prefer DATABASE_URL; if it's missing, start with sqlite instead of crashing.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    db_name = env("DB_NAME", default="")
    if db_name:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": db_name,
                "USER": env("DB_USER", default="postgres"),
                "PASSWORD": env("DB_PASSWORD", default=""),
                "HOST": env("DB_HOST", default="localhost"),
                "PORT": env("DB_PORT", default="5432"),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = (
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.azuread.AzureADOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)

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

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary (optional) for media storage in production.
CLOUDINARY_URL = env("CLOUDINARY_URL", default="")
if CLOUDINARY_URL:
    CLOUDINARY_STORAGE = {
        "CLOUDINARY_URL": CLOUDINARY_URL,
    }
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=60),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
_default_cors = ["http://localhost:3000", "http://127.0.0.1:3000"]
_raw_cors = env.list("CORS_ALLOWED_ORIGINS", default=_default_cors)
_cleaned_cors = [_clean_origin(origin) for origin in _raw_cors]

frontend_origin = _clean_origin(FRONTEND_URL)
if frontend_origin:
    _cleaned_cors.append(frontend_origin)

CORS_ALLOWED_ORIGINS = _unique(
    [origin for origin in _cleaned_cors if _is_valid_origin(origin)]
)
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)

_raw_csrf = env.list("CSRF_TRUSTED_ORIGINS", default=[])
_cleaned_csrf = [_clean_origin(origin) for origin in _raw_csrf]
if frontend_origin:
    _cleaned_csrf.append(frontend_origin)
CSRF_TRUSTED_ORIGINS = _unique(
    [origin for origin in _cleaned_csrf if _is_valid_origin(origin)]
)

# Social Auth (Google & Microsoft)

SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/api/social/redirect/"
SOCIAL_AUTH_LOGIN_ERROR_URL = "/api/social/error/"
SOCIAL_AUTH_REDIRECT_IS_HTTPS = env.bool("SOCIAL_AUTH_REDIRECT_IS_HTTPS", default=not DEBUG)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env("GOOGLE_CLIENT_ID", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ["email", "profile"]
SOCIAL_AUTH_AZUREAD_OAUTH2_KEY = env("MICROSOFT_CLIENT_ID", default="")
SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET = env("MICROSOFT_CLIENT_SECRET", default="")
SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID = env("MICROSOFT_TENANT_ID", default="common")
SOCIAL_AUTH_AZUREAD_OAUTH2_SCOPE = ["openid", "email", "profile"]
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [
    urlparse(FRONTEND_URL).hostname
] if frontend_origin else []
SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "users.social_pipeline.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="").replace(" ", "")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
_default_from_email = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)
if _default_from_email in ("", "EMAIL_HOST_USER"):
    _default_from_email = EMAIL_HOST_USER
DEFAULT_FROM_EMAIL = _default_from_email

# Email provider selection:
# - Local/default: SMTP
# - Render default: SendGrid (HTTP API), unless overridden by EMAIL_PROVIDER
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="sendgrid" if is_render else "smtp").lower()
SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")
SENDGRID_FROM_EMAIL = env("SENDGRID_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)

BACKEND_BASE_URL = env("BACKEND_BASE_URL", default="http://localhost:8000")
WHATSAPP_PROVIDER = env("WHATSAPP_PROVIDER", default="mock")
WHATSAPP_LINK_TTL_SECONDS = env.int("WHATSAPP_LINK_TTL_SECONDS", default=7 * 24 * 60 * 60)
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_WHATSAPP_FROM = env("TWILIO_WHATSAPP_FROM", default="")

MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default="")
MPESA_PASSKEY = env("MPESA_PASSKEY", default="")
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", default="")
MPESA_BASE_URL = env("MPESA_BASE_URL", default="https://sandbox.safaricom.co.ke")
MPESA_TRANSACTION_TYPE = env("MPESA_TRANSACTION_TYPE", default="CustomerPayBillOnline")

ETIMS_API_URL = env("ETIMS_API_URL", default="")
ETIMS_API_KEY = env("ETIMS_API_KEY", default="")
ETIMS_TIMEOUT = env.int("ETIMS_TIMEOUT", default=20)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
