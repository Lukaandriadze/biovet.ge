"""
Django settings for config project.

საიდუმლო მონაცემები იკითხება .env ფაილიდან (იხილე .env.example).
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------
# .env ჩამტვირთავი (დამატებითი ბიბლიოთეკა არ სჭირდება)
# ------------------------------------------------------------------
def _load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# ------------------------------------------------------------------
# ძირითადი უსაფრთხოება
# ------------------------------------------------------------------
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY არ არის მითითებული (.env ფაილში).')


if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
ALLOWED_HOSTS = [
    "biovet.com.ge",
    "www.biovet.com.ge",
    "biovet-ge.onrender.com",
]
CSRF_TRUSTED_ORIGINS = [
    "https://biovet.com.ge",
    "https://www.biovet.com.ge",
]
# ------------------------------------------------------------------
# Application definition
# ------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'products',
    'categories',
    'AI',
    "cart.apps.CartConfig",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ------------------------------------------------------------------
# Database
# ------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
_database_url = os.environ.get('DATABASE_URL', '').strip()
if _database_url:
    from urllib.parse import parse_qs, unquote, urlparse

    _db = urlparse(_database_url)
    _db_query = {k: v[0] for k, v in parse_qs(_db.query).items()}
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _db.path.lstrip('/'),
        'USER': unquote(_db.username or ''),
        'PASSWORD': unquote(_db.password or ''),
        'HOST': _db.hostname or '',
        'PORT': _db.port or '',
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'sslmode': _db_query['sslmode']} if 'sslmode' in _db_query else {},
    }

# ------------------------------------------------------------------
# Auth (მხოლოდ ადმინ-პანელისთვის)
# ------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]



# ------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------
# Static / media
# ------------------------------------------------------------------

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ------------------------------------------------------------------
# Email
# ------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')   # Gmail App Password
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    f'Biovet <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else 'Biovet <no-reply@localhost>',
)


# ------------------------------------------------------------------
# Telegram / Gemini
# ------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

GEMINI_API_KEY_1 = os.environ.get('GEMINI_API_KEY_1', '')
