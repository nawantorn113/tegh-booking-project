from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-me-please'

# SECURITY WARNING: don't run with debug turned on in production!
# บน Server จริง ควรเปลี่ยนเป็น False แต่ตอนนี้เปิด True ไว้ก่อนเผื่อแก้บั๊ก
DEBUG = False

# อนุญาตให้ PythonAnywhere เข้าถึงได้
ALLOWED_HOSTS = ['user01.pythonanywhere.com', 'localhost', '127.0.0.1']

# อนุญาตให้ LINE Webhook ส่งข้อมูลเข้ามาได้
CSRF_TRUSTED_ORIGINS = [
    'https://user01.pythonanywhere.com',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 3rd Party Apps (ต้องลง pip install เพิ่มใน Console)
    'dal',
    'dal_select2',
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',

    # My Apps
    'booking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # WhiteNoise ต้องอยู่นี่
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',          # โฟลเดอร์ template กลาง
            BASE_DIR / 'booking/templates',  # โฟลเดอร์ template ของแอป
        ],
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

WSGI_APPLICATION = 'mysite.wsgi.application'


# Database
# ใช้ SQLite สำหรับ PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# โฟลเดอร์ที่เก็บ Static file ขณะพัฒนา
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'booking/static',
]

# [สำคัญสำหรับ PythonAnywhere] โฟลเดอร์ปลายทางที่รวบรวมไฟล์ Static จริง
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (Uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================
# Custom Settings
# ==============================================

# 1. Login/Logout
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# 2. Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# 3. Email Settings (จำลองการส่งใน Console เพราะยังไม่มี SMTP จริง)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'ระบบจองห้องประชุม <no-reply@tegh.com>'

# 4. LINE Messaging API Settings
# --------------------------------------------------
LINE_CHANNEL_SECRET = '297c1a8c67e6a6f7fb6849e2674e46f7'
LINE_CHANNEL_ACCESS_TOKEN = 'GnoNpDFeLx48BmqV+nv8I10XsdfSx0wqS3V6W9ZXnvBY3vEAav1fWM/Vy0aPYeUXQtcrLYzuJNTnNtnuQbgmXcGimHBBLz1pt/cyVbWi6yqzdIC9mzfR2CrHksKQOL/nDui7SieM0zRHt+6Pe8DGKQdB04t89/1O/w1cDnyilFU='
# --------------------------------------------------

# 5. Azure / Outlook
AZURE_CLIENT_ID = 'YOUR_AZURE_CLIENT_ID'
AZURE_CLIENT_SECRET = 'YOUR_AZURE_CLIENT_SECRET'
AZURE_REDIRECT_URI = 'http://127.0.0.1:8000/outlook/callback/'