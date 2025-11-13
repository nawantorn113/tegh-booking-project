# booking/apps.py

from django.apps import AppConfig

# ❌ เราลบ import reportlab, os, settings ทิ้งไปแล้ว
#    เพราะ WeasyPrint (ใน views.py) ไม่จำเป็นต้องใช้


class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booking'
