"""
Django settings for mcm_admission project.
Production-ready for Hostinger VPS.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
# dj_database_url can stay installed, but not used in production
import dj_database_url

load_dotenv()

# BASE DIR
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'changeme-insecure-key')
DEBUG = True
# IMPORTANT: Add your VPS server IP here
raw_hosts = os.getenv('DJANGO_ALLOWED_HOSTS')
if raw_hosts:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',')]
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost", "72.61.120.154"]

CSRF_TRUSTED_ORIGINS = [
    "http://72.61.120.154",
    "https://72.61.120.154",
]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
# APPS
INSTALLED_APPS = [
    'accounts',
    'admissions',
    'notifications',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',
]

AUTH_USER_MODEL = 'accounts.User'

# MIDDLEWARE
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise must be directly after SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mcm_admission.urls'

# TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mcm_admission.wsgi.application'

# ============================
# ⭐ UPDATED DATABASE (VPS)
# ============================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mcmdb',
        'USER': 'mcm_user',
        'PASSWORD': 'mcm_pass_@@@',   # your real password
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ============================
# PASSWORD VALIDATION
# ============================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# INTERNATIONALIZATION
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ============================
# EMAIL CONFIG
# ============================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465
EMAIL_USE_TLS = False
EMAIL_USE_SSL = True

EMAIL_SSL_CERTFILE = None
EMAIL_SSL_KEYFILE = None

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

DEFAULT_FROM_EMAIL = f"Military College Murree <{EMAIL_HOST_USER}>"

# ============================
# STATIC & MEDIA
# ============================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# WhiteNoise compressed storage
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# LOGIN/LOGOUT
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/admissions/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# AUTH BACKENDS
AUTHENTICATION_BACKENDS = [
    'accounts.backends.UsernameOrEmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ============================
# CELERY CONFIG
# ============================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# CONTACT INFO
ADMISSION_CONTACT_EMAIL = os.getenv('ADMISSION_CONTACT_EMAIL', 'mcmcoord@gmail.com')
ADMISSION_CONTACT_PHONE = os.getenv('ADMISSION_CONTACT_PHONE', '051-3752010')

# DEFAULT PRIMARY KEY
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

