from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # บอกให้ส่งต่อ URL ทั้งหมดไปให้แอป booking จัดการ
    path('', include('booking.urls')),
]