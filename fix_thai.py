import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from booking.models import AuditLog  # แก้ booking เป็นชื่อแอปของคุณที่มี model นี้

def fix_text(text):
    if not text: return text
    try:
        # ลองแปลงกลับจาก encoding ที่ผิด (cp1252 -> utf-8)
        return text.encode('cp1252').decode('utf-8')
    except:
        return text

print("กำลังซ่อมแซมภาษาไทย...")
count = 0
for log in AuditLog.objects.all():
    original_action = log.action
    original_details = log.details
    
    fixed_action = fix_text(original_action)
    fixed_details = fix_text(original_details)
    
    if original_action != fixed_action or original_details != fixed_details:
        log.action = fixed_action
        log.details = fixed_details
        log.save()
        count += 1
        print(f"แก้แล้ว: {fixed_details}")

print(f"เสร็จสิ้น! แก้ไขไปทั้งหมด {count} รายการ")