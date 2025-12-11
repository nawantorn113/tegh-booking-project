from django.contrib import admin
from .models import Room, Booking, AuditLog, OutlookToken, Equipment

# 1. ตั้งค่าการแสดงผล Room (ห้องประชุม)
class RoomAdmin(admin.ModelAdmin):
    # แสดงคอลัมน์: ชื่อ, อาคาร, ความจุ, สถานะปิดปรับปรุง, และ *ต้องรออนุมัติ*
    list_display = ('name', 'building', 'floor', 'capacity', 'is_maintenance', 'requires_approval')
    
    # ตัวกรองด้านขวา
    list_filter = ('building', 'is_maintenance', 'requires_approval')
    
    # ช่องค้นหา
    search_fields = ('name', 'building')
    
    # *สำคัญ* ทำให้ติ๊กถูกแก้ไขค่าได้เลยจากหน้าตาราง (สะดวกมาก)
    list_editable = ('is_maintenance', 'requires_approval')

# 2. ตั้งค่าการแสดงผล Booking (การจอง)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'user', 'start_time', 'end_time', 'status', 'participant_count')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'user__username', 'user__first_name', 'room__name')
    ordering = ('-start_time',)
    
    # (Optional) ทำให้ดูง่ายขึ้นว่าใครสร้างรายการเมื่อไหร่
    date_hierarchy = 'start_time'

# 3. ตั้งค่า Audit Log (ประวัติการใช้งานระบบ)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'ip_address', 'timestamp')
    list_filter = ('action',)
    search_fields = ('user__username', 'details')
    readonly_fields = ('timestamp',) # ห้ามแก้ไขเวลา

# 4. ลงทะเบียน Model ทั้งหมดเข้าสู่ระบบ Admin
admin.site.register(Room, RoomAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
admin.site.register(OutlookToken)

# ถ้ามี Model Equipment (อุปกรณ์) ด้วย ให้เปิดบรรทัดนี้ครับ
try:
    admin.site.register(Equipment)
except admin.sites.AlreadyRegistered:
    pass