from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('select2/', include('django_select2.urls')), # สำหรับ Autocomplete
    path('', include('booking.urls')), # URL ของแอป booking
]

# --- เพิ่มการเสิร์ฟ Static/Media ตอน DEBUG=True ---
if settings.DEBUG:
    # Use STATICFILES_DIRS if it exists
    static_root = settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT
    urlpatterns += static(settings.STATIC_URL, document_root=static_root)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
