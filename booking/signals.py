from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking

# ตัวแปรนี้ใช้เก็บสถานะ "ก่อน" ที่จะบันทึก
# เราใช้มันเพื่อเช็คว่าสถานะเพิ่ง "เปลี่ยน" หรือไม่
# (เก็บเป็น global dict ชั่วคราวเพื่อง่ายต่อการอธิบาย)
previous_status = {}

@receiver(post_save, sender=Booking)
def send_booking_notification(sender, instance, created, **kwargs):
    """
    ฟังก์ชันนี้จะทำงานอัตโนมัติ "หลังจาก" ที่ Booking object ถูก save
    """
    
    # ดึงสถานะก่อนหน้า (ถ้ามี)
    old_status = previous_status.get(instance.id)
    new_status = instance.status

    # ตรวจสอบว่าเป็นการ "สร้างใหม่" หรือไม่
    if created:
        # --- 1. กรณี: สร้างการจองใหม่ (PENDING) ---
        subject = f"[จองห้องใหม่] {instance.title} (รออนุมัติ)"
        
        # เตรียม context เพื่อส่งไปที่ template
        context = {
            'booking': instance,
            'room': instance.room,
            'user': instance.user,
        }
        
        # Render ข้อความจาก Template (เราจะสร้าง template นี้ในขั้นตอนถัดไป)
        message = render_to_string('emails/new_booking_admin.txt', context)
        html_message = render_to_string('emails/new_booking_admin.html', context)

        # 💡 [แก้ไข] ใส่อีเมล Admin หรือ ผู้อนุมัติห้อง (instance.room.approver.email)
        admin_email = 'admin@yourcompany.com' 
        
        # ส่งเมล!
        send_mail(
            subject,
            message, # ข้อความแบบ text ธรรมดา
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            html_message=html_message # ข้อความแบบ HTML สวยๆ
        )

    # ตรวจสอบว่าเป็นการ "อัปเดต" และสถานะ "เพิ่งเปลี่ยน"
    elif old_status != new_status:
        
        user_email = instance.user.email
        if not user_email: # ถ้า user ไม่มีอีเมล ก็ไม่ต้องส่ง
            return

        # --- 2. กรณี: การจองถูก "อนุมัติ" ---
        if new_status == 'APPROVED':
            subject = f"[อนุมัติแล้ว] การจองห้อง '{instance.title}' ของคุณ"
            message = f"การจองห้อง {instance.room.name} ของคุณได้รับการอนุมัติแล้ว"
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])

        # --- 3. กรณี: การจองถูก "ปฏิเสธ" ---
        elif new_status == 'REJECTED':
            subject = f"[ไม่อนุมัติ] การจองห้อง '{instance.title}' ของคุณ"
            message = f"ขออภัย, การจองห้อง {instance.room.name} ของคุณไม่ได้รับการอนุมัติ"
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])

    # อัปเดตสถานะล่าสุดใน dict
    previous_status[instance.id] = new_status