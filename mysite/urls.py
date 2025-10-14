# mysite/urls.py

from django.contrib import admin
from django.urls import path, include # <-- ตรวจสอบว่ามี include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # บรรทัดนี้จะบอกว่า "ถ้ามีใครเข้ามาที่เว็บ ให้ส่งต่อไปให้ booking/urls.py จัดการ"
    path('', include('booking.urls')), 
]