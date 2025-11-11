from django.apps import AppConfig

class BookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'booking'

    # 💡 เพิ่มฟังก์ชัน ready() นี้เข้าไป
    def ready(self):
        import booking.signals  # สั่ง import signals ของเรา