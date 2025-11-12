# booking/apps.py

from django.apps import AppConfig
import os
from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booking'

    def ready(self):
        # โค้ดนี้จะทำงาน 1 ครั้ง ตอนที่เซิร์ฟเวอร์เปิด
        print("--- [BookingConfig] กำลังลงทะเบียนฟอนต์ภาษาไทย ---")
        try:
            # ใช้ Path ที่ถูกต้อง (ระดับเดียวกับ manage.py)
            font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Sarabun-Regular.ttf')
            
            if os.path.exists(font_path):
                # ลงทะเบียนฟอนต์ โดยตั้งชื่อให้มันว่า 'Sarabun'
                pdfmetrics.registerFont(TTFont('Sarabun', font_path))
                print("--- [BookingConfig] ลงทะเบียนฟอนต์ Sarabun-Regular.ttf สำเร็จ ---")
            else:
                print("--- [BookingConfig] หา Sarabun-Regular.ttf ไม่เจอ, ลองหา THSarabunNew.ttf ---")
                font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'THSarabunNew.ttf')
                
                if os.path.exists(font_path):
                     pdfmetrics.registerFont(TTFont('Sarabun', font_path)) # ยังคงตั้งชื่อว่า 'Sarabun'
                     print("--- [BookingConfig] ลงทะเบียนฟอนต์ THSarabunNew.ttf สำเร็จ (ในชื่อ 'Sarabun') ---")
                else:
                    print("!!! [BookingConfig] CRITICAL: ไม่พบไฟล์ฟอนต์ไทยทั้งสองไฟล์ !!!")
        
        except Exception as e:
            print(f"!!! [BookingConfig] ERROR: เกิดข้อผิดพลาดตอนลงทะเบียนฟอนต์: {e}")