from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-me-please'

# =========================================================
# [ตั้งค่าความปลอดภัยสำหรับ Production]
# =========================================================
DEBUG = False  # [แก้ไข] ปิดโหมด Debug เมื่อขึ้น Server จริง

ALLOWED_HOSTS = ['*']  # อนุญาตให้เข้าถึงได้จากทุก IP หรือ Domain

# ใส่ Domain/IP ของเครื่อง Server ที่นี่ด้วย (ถ้าใช้ HTTPS)
CSRF_TRUSTED_ORIGINS = [
    'https://chirographic-buffy-overfaithfully.ngrok-free.dev', 
    # 'https://192.168.1.xxx', # (ตัวอย่าง) ใส่ IP ของเครื่อง Server
]

# Application definition
INSTALLED_APPS = [
    # 3rd Party Apps
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    
    # My Apps
    'booking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # [สำคัญ] ช่วยเสิร์ฟไฟล์ Static บน IIS/Server ได้ดีมาก
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
            BASE_DIR / 'templates',
            BASE_DIR / 'booking/templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'booking.context_processors.menu_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

# =========================================================
# [ฐานข้อมูล SQL Server]
# =========================================================
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'teghmeet_room',
        'USER': 'sa',
        'PASSWORD': 'liaMilleMig#2020',
        'HOST': '192.168.2.254',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'extra_params': 'TrustServerCertificate=yes',
        },
    }
}


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

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

# =========================================================
# [Static & Media Files]
# =========================================================
STATIC_URL = '/static/'

# โฟลเดอร์ที่เก็บไฟล์ Static ขณะพัฒนา (Development)
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'booking/static',
]

# [สำคัญ] โฟลเดอร์ปลายทางที่จะรวบรวมไฟล์ทั้งหมดไปไว้เมื่อขึ้น Server
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ใช้ WhiteNoise ช่วยบีบอัดและเสิร์ฟไฟล์
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom Settings
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'public_calendar'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'ระบบจองห้องประชุม <no-reply@tegh.com>'

# LINE & Azure Settings
LINE_CHANNEL_SECRET = '297c1a8c67e6a6f7fb6849e2674e46f7'
LINE_CHANNEL_ACCESS_TOKEN = 'GnoNpDFeLx48BmqV+nv8I10XsdfSx0wqS3V6W9ZXnvBY3vEAav1fWM/Vy0aPYeUXQtcrLYzuJNTnNtnuQbgmXcGimHBBLz1pt/cyVbWi6yqzdIC9mzfR2CrHksKQOL/nDui7SieM0zRHt+6Pe8DGKQdB04t89/1O/w1cDnyilFU='
AZURE_CLIENT_ID = 'YOUR_AZURE_CLIENT_ID'
AZURE_CLIENT_SECRET = 'YOUR_AZURE_CLIENT_SECRET'
AZURE_REDIRECT_URI = 'http://127.0.0.1:8000/outlook_callback' 
# หมายเหตุ: ถ้าขึ้น Server จริง อย่าลืมแก้ 127.0.0.1 เป็น IP หรือ Domain ของ Server ด้วยนะครับ