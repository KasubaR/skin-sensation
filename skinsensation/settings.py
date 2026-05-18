"""
Django settings for skinsensation project.

Aligned with requirements.txt: Django 4.2 (Python 3.9 on production).

https://docs.djangoproject.com/en/4.2/topics/settings/
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Set DJANGO_SECRET_KEY in cPanel → Setup Python App → environment variables.
# For local dev, a fallback insecure key is used automatically.
_IS_PRODUCTION = os.environ.get('DJANGO_ENV') == 'production'
if _IS_PRODUCTION:
    SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
else:
    SECRET_KEY = os.environ.get(
        'DJANGO_SECRET_KEY',
        'django-insecure-local-dev-only-do-not-use-in-production',
    )

# SECURITY WARNING: don't run with debug turned on in production!
# When DEBUG is False, Django does not serve files from STATICFILES_DIRS — CSS/JS under /static/ will 404 unless you run collectstatic and serve STATIC_ROOT (or use WhiteNoise, etc.).
# Local development: leave DJANGO_ENV unset or set anything other than 'production'.
DEBUG = not _IS_PRODUCTION

if _IS_PRODUCTION:
    ALLOWED_HOSTS = ['skinsensationspa.com', 'www.skinsensationspa.com']

    # cPanel terminates SSL at the web server; trust X-Forwarded-Proto for HTTPS detection.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'accounts',
    'services',
    'bookings',
    'payments',
    'notifications',
    'dashboard',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'skinsensation.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'skinsensation.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if _IS_PRODUCTION:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'qualrijx_skin_sensation',
            'USER': 'qualrijx_skin_sensation',
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': 'localhost',
            'PORT': '3306',
            'CONN_MAX_AGE': 60,
            'OPTIONS': {
                'sql_mode': 'STRICT_TRANS_TABLES',
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/appointments/'
LOGOUT_REDIRECT_URL = '/'

ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
# Registered accounts must verify email before login; guest bookings still use the booking form email.
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if not DEBUG else 'http'

if _IS_PRODUCTION:
    # cPanel SMTP: mail.skinsensationspa.com port 465 (implicit SSL).
    # Set EMAIL_HOST_PASSWORD in cPanel → Setup Python App → environment variables.
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mail.skinsensationspa.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '465'))
    EMAIL_USE_SSL = True   # port 465 — implicit SSL, mutually exclusive with EMAIL_USE_TLS
    EMAIL_USE_TLS = False
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'info@skinsensationspa.com')
    EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'info@skinsensationspa.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Contact-form enquiries are forwarded to this address.
# Set CONTACT_EMAIL in the environment (cPanel → Setup Python App → env vars).
_contact_email = os.environ.get('CONTACT_EMAIL', 'info@skinsensationspa.com')
MANAGERS = [('Skin Sensation', _contact_email)]

SPA_WHATSAPP_E164 = os.environ.get('SPA_WHATSAPP_E164', '260973407110')
SPA_PHONE_DISPLAY = os.environ.get('SPA_PHONE_DISPLAY', '+260 973 407 110')
SPA_TIME_ZONE = os.environ.get('SPA_TIME_ZONE', 'Africa/Lusaka')


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = SPA_TIME_ZONE

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache — used by django-ratelimit and general caching.
# FileBasedCache is shared across Passenger worker processes on cPanel.
# LocMemCache (Django default) is per-process and sufficient for local dev.
if _IS_PRODUCTION:
    CACHE_DIR = BASE_DIR / 'cache'
    CACHE_DIR.mkdir(exist_ok=True)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': str(CACHE_DIR),
        }
    }

    LOG_DIR = BASE_DIR / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': LOG_DIR / 'django.log',
                'maxBytes': 5 * 1024 * 1024,
                'backupCount': 3,
                'formatter': 'verbose',
            },
        },
        'root': {
            'handlers': ['file'],
            'level': 'WARNING',
        },
        'loggers': {
            'django.request': {
                'handlers': ['file'],
                'level': 'ERROR',
                'propagate': False,
            },
            'notifications': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
