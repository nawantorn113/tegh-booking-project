# mysite/urls.py
# [ฉบับเต็ม - ตรวจสอบ MEDIA_URL]

from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static function

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('select2/', include('django_select2.urls')), # Uncomment if using dal_select2
    path('', include('booking.urls')), # Your app's URLs
]

# --- Serve Static and Media files during development (DEBUG=True) ---
if settings.DEBUG:
    static_root = settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT
    urlpatterns += static(settings.STATIC_URL, document_root=static_root)
    # --- ตรวจสอบว่าบรรทัดนี้มีอยู่ และถูกต้อง ---
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # --- ------------------------------- ---
# --- End Serving Static/Media ---