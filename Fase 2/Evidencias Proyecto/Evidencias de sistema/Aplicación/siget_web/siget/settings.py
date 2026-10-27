"""Configuración de Django para SIGET."""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR.parent / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DJANGO_DEBUG")

env = environ.Env(
    DJANGO_ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
)

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "usuarios",
    "activos",
    "asignaciones",
    "repuestos",
    "tickets",
    "ordenes_trabajo",
    "notificaciones",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "siget.urls"

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

WSGI_APPLICATION = "siget.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
        "TEST": {"NAME": env.str("POSTGRES_TEST_DB", default="test_" + env.str("POSTGRES_DB"))},
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "es-cl"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# AUTH0

AUTH0_DOMAIN = env.str("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = env.str("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = env.str("AUTH0_CLIENT_SECRET")
AUTH0_DB_CONNECTION = env.str("AUTH0_DB_CONNECTION", default="Username-Password-Authentication")

AUTH0_MGMT_CLIENT_ID = env.str("AUTH0_MGMT_CLIENT_ID", default=AUTH0_CLIENT_ID)
AUTH0_MGMT_CLIENT_SECRET = env.str("AUTH0_MGMT_CLIENT_SECRET", default=AUTH0_CLIENT_SECRET)
AUTH0_MGMT_AUDIENCE = env.str(
    "AUTH0_MGMT_AUDIENCE",
    default=f"https://{AUTH0_DOMAIN}/api/v2/" if AUTH0_DOMAIN else "",
)

AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else ""
AUTH0_METADATA_URL = f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration" if AUTH0_DOMAIN else ""

# Access tokens de la API de SIGET (aplicación de Escritorio, Authorization Code + PKCE).
# AUTH0_API_AUDIENCE es el "Identifier" de la API registrada en Auth0. Si está vacío,
# la autenticación Bearer queda deshabilitada y el portal Web funciona igual.
AUTH0_API_AUDIENCE = env.str("AUTH0_API_AUDIENCE", default="")
# client_id de las aplicaciones autorizadas a llamar la API (claim azp). Vacío = sin restricción.
AUTH0_API_ALLOWED_CLIENT_IDS = [
    client_id.strip() for client_id in env.str("AUTH0_API_ALLOWED_CLIENT_IDS", default="").split(",") if client_id.strip()
]
AUTH0_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else ""
AUTH0_JWKS_CACHE_SEGUNDOS = env.int("AUTH0_JWKS_CACHE_SEGUNDOS", default=600)
AUTH0_TOKEN_LEEWAY = env.int("AUTH0_TOKEN_LEEWAY", default=10)
AUTH0_HTTP_TIMEOUT = env.int("AUTH0_HTTP_TIMEOUT", default=5)

LOGIN_URL = "/auth/login/"
LOGOUT_REDIRECT_URL = "/"


REST_FRAMEWORK = {
    # El Bearer se evalúa primero solo si la petición lo incluye; sin ese encabezado
    # se mantiene la sesión Web con CSRF obligatorio.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "usuarios.authentication.SigetAccessTokenAuthentication",
        "usuarios.authentication.SigetSessionAuthentication",
    ],
    "EXCEPTION_HANDLER": "siget.exceptions.api_exception_handler",
}

TEST_RUNNER = "siget.testing.PostgreSQLTestRunner"

SIGET_PUBLIC_URL = env.str("SIGET_PUBLIC_URL", default="").rstrip("/")

# Correo transaccional: secretos solo en el backend y despacho mediante Resend.
RESEND_API_KEY = env.str("RESEND_API_KEY", default="")
RESEND_FROM_EMAIL = env.str("RESEND_FROM_EMAIL", default="")  # Debe ser un remitente verificado en Resend.
RESEND_TIMEOUT_SECONDS = env.int("RESEND_TIMEOUT_SECONDS", default=10)
RESEND_MAX_ATTEMPTS = env.int("RESEND_MAX_ATTEMPTS", default=5)
RESEND_RETRY_SECONDS = env.int("RESEND_RETRY_SECONDS", default=60)
