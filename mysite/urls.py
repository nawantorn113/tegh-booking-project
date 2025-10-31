from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('select2/', include('django_select2.urls')), 
    path('', include('booking.urls')), 
]

# [แก้ไข] ตอน DEBUG=True, ให้ Django เสิร์ฟเฉพาะ Media Files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)