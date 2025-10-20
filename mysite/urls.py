# mysite/urls.py
# [Full Code - Corrected Static/Media Serving]

from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static function

urlpatterns = [
    path('admin/', admin.site.urls), # Django admin site
    # path('select2/', include('django_select2.urls')), # Uncomment if you reinstall and use django-autocomplete-light
    path('', include('booking.urls')), # Include your app's URLs
]

# --- Serve Static and Media files during development (DEBUG=True) ---
if settings.DEBUG:
    # Determine the correct root for static files based on settings
    static_root = settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT
    urlpatterns += static(settings.STATIC_URL, document_root=static_root)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# --- End Serving Static/Media ---
