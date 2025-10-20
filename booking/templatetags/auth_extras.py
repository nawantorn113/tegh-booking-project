# booking/templatetags/auth_extras.py
from django import template
from django.contrib.auth.models import Group

register = template.Library() # สร้างตัวแปร register

@register.filter(name='is_admin') # ลงทะเบียน filter ชื่อ is_admin
def is_admin(user):
    """ตรวจสอบว่า user อยู่ในกลุ่ม 'Admin' หรือเป็น superuser หรือไม่"""
    if user.is_authenticated:
        try:
            # ตรวจสอบว่าเป็น superuser หรืออยู่ในกลุ่ม Admin
            return user.is_superuser or Group.objects.get(name='Admin') in user.groups.all()
        except Group.DoesNotExist:
            return user.is_superuser # ถ้ากลุ่ม Admin ไม่มี ให้เช็คแค่ superuser
    return False

@register.filter(name='is_approver_or_admin') # ลงทะเบียน filter ชื่อ is_approver_or_admin
def is_approver_or_admin(user):
    """ตรวจสอบว่า user อยู่ในกลุ่ม 'Approver' หรือ 'Admin' หรือเป็น superuser หรือไม่"""
    if user.is_authenticated:
        try:
            # ตรวจสอบว่าเป็น superuser หรืออยู่ในกลุ่ม Admin หรือ Approver
            is_in_group = user.groups.filter(name__in=['Admin', 'Approver']).exists()
            return user.is_superuser or is_in_group
        except Group.DoesNotExist:
             # ถ้ากลุ่มไม่มี (ซึ่งไม่ควรเกิด) ให้เช็คแค่ superuser
            return user.is_superuser
    return False

# --- หมายเหตุ ---
# อย่าลืมสร้าง Group ชื่อ 'Admin' และ 'Approver'
# ในหน้า Django Admin (/admin/auth/group/) ด้วยนะครับ