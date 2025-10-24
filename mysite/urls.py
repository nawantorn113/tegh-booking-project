# mysite/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- ❌ ต้องไม่มี path('dal/', ...) ที่นี่ ❌ ---
    
    path('', include('booking.urls')), # URL ของแอป booking
]

if settings.DEBUG:
    try:
        static_root = settings.STATICFILES_DIRS[0]
    except (IndexError, AttributeError):
        static_root = settings.STATIC_ROOT
    
    if static_root:
        urlpatterns += static(settings.STATIC_URL, document_root=static_root)
        
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)