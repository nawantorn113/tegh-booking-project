from pathlib import Path
import os # 💡 [เพิ่ม] Import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-=+c(!!5a&e&d#p#^g$q@d#... (ใช้คีย์เดิมของคุณ)'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 'django_xhtml2pdf', # <--- 1. [แก้ไข] ลบบรรทัดนี้ออก (นี่คือตัวที่ทำให้แครช)
    
    'booking',
    'dal',
    'dal_select2',
    
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
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


# ❌ [แก้ไข] ลบส่วน STATIC_URL / STATICFILES_DIRS ที่ซ้ำซ้อนตรงนี้ออก
# STATIC_URL = '/static/'
# STATICFILES_DIRS = [
#     os.path.join(BASE_DIR, 'static'),
# ]

ROOT_URLCONF = 'mysite.urls'  # 💡 ตรวจสอบชื่อโฟลเดอร์โปรเจกต์ของคุณตรงนี้ด้วย (ปกติอาจเป็น mysite หรือ tegh_booking)

# 💡 [แก้ไข] เพิ่ม Path ของ booking/templates/
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        
        'DIRS': [
            BASE_DIR / 'templates',
            os.path.join(BASE_DIR, 'booking', 'templates'), # 💡 เพิ่มบรรทัดนี้
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

WSGI_APPLICATION = 'mysite.wsgi.application' # ตรวจสอบชื่อโฟลเดอร์โปรเจกต์ของคุณตรงนี้ด้วย


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'tegh_booking_db',
        
        'USER': '',
        'PASSWORD': '',
        
        'HOST': 'localhost\\SQLEXPRESS',
        'PORT': '',              

        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'trusted_connection': 'yes', 
            'TrustServerCertificate': 'yes', 
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# -----------------------------------------------
# 💡 [แก้ไข] EMAIL CONFIGURATION (โหมดทดสอบ)
# -----------------------------------------------
# เปลี่ยนเป็น "พิมพ์อีเมลออกทาง Console" เพื่อทดสอบ
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'ระบบจองห้องประชุม <no-reply@tegh.com>'
# -----------------------------------------------


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Bangkok'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [ BASE_DIR / "static" ] # <--- 2. [ถูกต้อง] เก็บอันนี้ไว้ (อันบนถูกลบไปแล้ว)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

X_FRAME_OPTIONS = 'SAMEORIGIN'

# Crispy Forms Settings
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# =========================================================================
# 💡 [ใหม่] MICROSOFT AZURE / OUTLOOK CALENDAR INTEGRATION SETTINGS
# =========================================================================

# 💡 1. Client ID (Application ID from Azure)
AZURE_CLIENT_ID = "YOUR_AZURE_CLIENT_ID_HERE" 

# 💡 2. Client Secret (The secret value generated in Azure AD)
AZURE_CLIENT_SECRET = "YOUR_AZURE_CLIENT_SECRET_HERE" 

# 💡 3. Redirect URI (Must exactly match the URI registered in Azure AD)
AZURE_REDIRECT_URI = 'http://127.0.0.1:8000/outlook/callback/' 


# =========================================================================
# 💡 [สำคัญ] เพิ่มส่วนนี้เพื่อแก้ปัญหา CSRF Error ของ ngrok
# =========================================================================
CSRF_TRUSTED_ORIGINS = [
    'https://chirographic-buffy-overfaithfully.ngrok-free.dev',
]
# =========================================================================

# ==============================================
# EMAIL SETTINGS (สำหรับทดสอบในเครื่อง)
# ==============================================

# ใช้วิธีนี้เพื่อ "จำลอง" การส่งเมล (ข้อความจะขึ้นใน Terminal แทนการส่งจริง)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# อีเมลผู้ส่ง (สมมติ)
DEFAULT_FROM_EMAIL = 'ระบบจองห้องประชุม <no-reply@tegh.com>'

# ==============================================
# ถ้าต้องการส่งจริง (เช่นใช้ Gmail) ให้เปิดคอมเมนต์ด้านล่างนี้แทน
# ==============================================
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-email@gmail.com'  # 👈 ใส่อีเมลจริง
# EMAIL_HOST_PASSWORD = 'xxxx xxxx xxxx xxxx'  # 👈 ใส่ App Password (ไม่ใช่รหัสผ่านปกติ)