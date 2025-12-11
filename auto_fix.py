import os
import django
from ftfy import fix_text

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

# แก้ booking เป็นชื่อแอปของคุณ
from booking.models import AuditLog

print("กำลังซ่อมแซมข้อความ...")
count = 0
for log in AuditLog.objects.all():
    # ใช้ ftfy ซ่อมข้อความให้อัตโนมัติ
    original_action = log.action
    original_details = log.details

    fixed_action = fix_text(original_action)
    fixed_details = fix_text(original_details)

    if original_action != fixed_action or original_details != fixed_details:
        log.action = fixed_action
        log.details = fixed_details
        log.save()
        count += 1

print(f"✅ ซ่อมเสร็จแล้วทั้งหมด {count} รายการ")