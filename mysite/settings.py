from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-me-please'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# อนุญาตให้เครื่องอื่น (มือถือ/LAN) เข้าถึงได้
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 📦 3rd Party Apps
    'dal',
    'dal_select2',
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',

    # 🏠 My Apps
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
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',          # โฟลเดอร์ template กลาง (ถ้ามี)
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
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# ⚠️ หมายเหตุ: ถ้าคุณใช้ MSSQL (SQL Server) ให้ใช้ Config เดิมของคุณตรงนี้แทน SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'  # หรือ 'th' ถ้าต้องการภาษาไทย
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',         # โฟลเดอร์ static กลาง
    BASE_DIR / 'booking/static', # โฟลเดอร์ static ของแอป
]

# Media files (Uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================
# ⚙️ Custom Settings (การตั้งค่าเพิ่มเติม)
# ==============================================

# 1. Login/Logout Redirect
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# 2. Crispy Forms (Bootstrap 5)
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# 3. Email Settings (สำหรับส่งแจ้งเตือน)
# ใช้ Console Backend (แสดงใน Terminal) สำหรับทดสอบ
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'ระบบจองห้องประชุม <no-reply@tegh.com>'

# ถ้าจะส่งจริงผ่าน Gmail ให้เปิดส่วนนี้และปิดด้านบน
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'

# 4. LINE Messaging API (สำหรับแจ้งเตือนไลน์)
# 🔑 นำรหัสที่คุณได้จาก LINE Developers มาใส่ตรงนี้
LINE_CHANNEL_ACCESS_TOKEN = '5a7ea5cdad04f6ac72b40e27922ae804'
LINE_CHANNEL_SECRET = ''

# 5. Azure / Outlook Integration (ถ้ามี)
AZURE_CLIENT_ID = 'YOUR_AZURE_CLIENT_ID'
AZURE_CLIENT_SECRET = 'YOUR_AZURE_CLIENT_SECRET'
AZURE_REDIRECT_URI = 'http://127.0.0.1:8000/outlook/callback/'