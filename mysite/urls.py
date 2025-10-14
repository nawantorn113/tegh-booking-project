# mysite/urls.py
# [แก้ไข] แก้ไขการจัดย่อหน้า (Indentation) และอักขระพิเศษทั้งหมด

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 1. เส้นทางสำหรับหน้า Admin ของ Django
    # เมื่อมีคนเข้ามาที่ http://.../admin/ ให้ไปที่ระบบ Admin
    path('admin/', admin.site.urls),

    # 2. เส้นทางสำหรับแอปพลิเคชันหลักของเรา
    # เมื่อมีคนเข้ามาที่ URL อื่นๆ ทั้งหมด (เช่น http://.../ หรือ http://.../login/)
    # ให้ส่งต่อไปให้ไฟล์ booking/urls.py เป็นคนจัดการต่อ
    path('', include('booking.urls')),
]

# --- ส่วนนี้คือส่วนที่คุณถามว่า "เพิ่มตรงไหน" ---
# 3. การตั้งค่าสำหรับแสดงไฟล์ Media (เช่น รูปโปรไฟล์) ในระหว่างการพัฒนา (DEBUG mode)
# ส่วนนี้จะถูกเพิ่ม "ต่อท้าย" urlpatterns ที่มีอยู่แล้ว
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)