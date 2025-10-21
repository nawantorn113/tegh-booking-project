# mysite/settings.py
# [Full Code - Corrected Static/Media Config]

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# Make sure to replace 'YOUR-SECRET-KEY' with a real, generated key
SECRET_KEY = 'django-insecure-YOUR-SECRET-KEY'
DEBUG = True # Keep True for development to see errors and serve static files
ALLOWED_HOSTS = [] # Keep empty for local development

# Application definition
INSTALLED_APPS = [
    # 'dal', # Temporarily removed - Add back if using django-autocomplete-light
    # 'dal_select2', # Temporarily removed - Add back if using django-autocomplete-light
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'booking', # Your application
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', # Handles session data
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', # Handles user authentication
    'django.contrib.messages.middleware.MessageMiddleware', # Handles flash messages
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mysite.urls' # Points to your main urls.py file

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # Location of base.html etc.
        'APP_DIRS': True, # Allows Django to find templates inside app directories
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth', # Adds user object to templates
                'django.contrib.messages.context_processors.messages', # Adds messages framework to templates
                'booking.context_processors.menu_context', # Your custom menu processor
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3', # Your SQLite database file
    }
}

# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/
LANGUAGE_CODE = 'th' # Set to Thai
TIME_ZONE = 'Asia/Bangkok' # Set your timezone
USE_I18N = True
USE_TZ = True # Recommended to keep True for timezone handling


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/
STATIC_URL = '/static/' # URL prefix for static files
STATICFILES_DIRS = [
    BASE_DIR / "static", # Directory where Django looks for your static files
]
STATIC_ROOT = BASE_DIR / 'staticfiles' # Directory where collectstatic gathers files (for production)

# Media files (User Uploads)
# https://docs.djangoproject.com/en/stable/howto/static-files/#serving-files-uploaded-by-a-user-during-development
MEDIA_URL = '/media/' # URL prefix for media files
MEDIA_ROOT = BASE_DIR / 'media' # Directory where uploaded files are stored


# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs
LOGIN_URL = 'login' # Name of the login URL pattern
LOGIN_REDIRECT_URL = 'dashboard' # Where to redirect after successful login
LOGOUT_REDIRECT_URL = 'login' # Where to redirect after logout

# Email configuration (using console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'webmaster@localhost'