import requests
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
# เปลี่ยน booking เป็นชื่อแอปของคุณ
from booking.models import Booking 

class Command(BaseCommand):
    help = 'แจ้งเตือนประชุมผ่าน LINE OA (Broadcast) ก่อน 30 นาที'

    def handle(self, *args, **kwargs):
        # ==============================================================================
        # 🔑 ตั้งค่า LINE OA (Messaging API)
        # ==============================================================================
        
        # 1. ไปเอา Channel Access Token จากหน้า LINE OA Manager -> Messaging API
        # (รหัสจะยาวมากๆ เลื่อนลงไปล่างสุดของหน้านั้น)
        CHANNEL_ACCESS_TOKEN = 'GnoNpDFeLx48BmqV+nv8I10XsdfSx0wqS3V6W9ZXnvBY3vEAav1fWM/Vy0aPYeUXQtcrLYzuJNTnNtnuQbgmXcGimHBBLz1pt/cyVbWi6yqzdIC9mzfR2CrHksKQOL/nDui7SieM0zRHt+6Pe8DGKQdB04t89/1O/w1cDnyilFU='
        
        # ==============================================================================

        now = timezone.now()
        future_point = now + timedelta(minutes=30)

        print(f"🤖 กำลังตรวจสอบรายการจอง (LINE OA Broadcast)...")

        # ค้นหาห้องที่ต้องแจ้งเตือน
        bookings = Booking.objects.filter(
            status='Approved', 
            start_time__lte=future_point,
            start_time__gt=now,
            is_notified=False
        )

        if bookings.count() == 0:
            self.stdout.write("✅ ไม่พบรายการที่ต้องแจ้งเตือน")
            return

        # ตั้งค่า Header
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
        }

        # URL สำหรับการส่งแบบ Broadcast (ส่งหาทุกคนที่เป็นเพื่อนกับบอท)
        url = 'https://api.line.me/v2/bot/message/broadcast'

        for booking in bookings:
            # ข้อความที่จะส่ง
            message_text = (
                f"🔴 แจ้งเตือน: ใกล้ถึงเวลาประชุม!\n"
                f"📌 หัวข้อ: {booking.title}\n"
                f"🏢 ห้อง: {booking.room}\n"
                f"⏰ เวลา: {booking.start_time.strftime('%H:%M')} น."
            )

            # ห่อจดหมาย (Payload)
            payload = {
                "messages": [
                    {
                        "type": "text",
                        "text": message_text
                    }
                ]
            }

            try:
                # ยิงข้อมูลไปที่ LINE
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                
                if response.status_code == 200:
                    booking.is_notified = True
                    booking.save()
                    self.stdout.write(self.style.SUCCESS(f"✅ แจ้งเตือนห้อง {booking.room} สำเร็จ"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ ส่งไม่ผ่าน: {response.text}"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))