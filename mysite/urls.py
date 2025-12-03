from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# เราจะสร้าง View ง่ายๆ เพื่อ Redirect คนที่เผลอเข้า /admin/ ให้กลับไปหน้า Dashboard
from django.shortcuts import redirect

def redirect_to_dashboard(request):
    return redirect('dashboard')

urlpatterns = [
    # หน้า Admin ของ Django 
    path('admin/', admin.site.urls), 
    
    # (Optional) ถ้าใครพยายามเข้า /admin/ ให้ดีดกลับไปหน้า Dashboard แทน
    path('admin/', redirect_to_dashboard),

    #  เชื่อมต่อกับ App Booking ของเรา
    path('', include('booking.urls')), 
]

# สำหรับโหลดไฟล์ Media (รูปภาพ) ตอนรันเครื่องตัวเอง
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)