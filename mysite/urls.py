from django.contrib import admin
from django.urls import path, include, re_path  # <--- เพิ่ม re_path
from django.conf import settings
from django.views.static import serve           # <--- เพิ่ม serve
from django.shortcuts import redirect

# ฟังก์ชัน Redirect ง่ายๆ
def redirect_to_dashboard(request):
    return redirect('dashboard')

urlpatterns = [
    # หน้า Admin
    path('admin/', admin.site.urls),
    
    # Redirect /admin/ ไป Dashboard (ถ้าต้องการ)
    # path('admin/', redirect_to_dashboard),

    # เชื่อมต่อกับ App Booking
    path('', include('booking.urls')),
]

# =========================================================
# [สำคัญ] ส่วนนี้บังคับให้เสิร์ฟรูปภาพและ Static Files เสมอ
# (ช่วยแก้ปัญหารูปหายเวลาขึ้นระบบจริง)
# =========================================================
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': settings.STATIC_ROOT,
    }),
]