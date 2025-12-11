from django.contrib import admin
from .models import Room, Booking, AuditLog, OutlookToken, Equipment

# -----------------------------------------------------------
# 1. ตั้งค่าการแสดงผล Room (ห้องประชุม)
# -----------------------------------------------------------
class RoomAdmin(admin.ModelAdmin):
    # แสดงคอลัมน์: ชื่อ, อาคาร, ชั้น, ความจุ, สถานะปิดปรับปรุง, และ *ต้องรออนุมัติ*
    list_display = ('name', 'building', 'floor', 'capacity', 'is_maintenance', 'requires_approval')
    
    # ตัวกรองด้านขวา
    list_filter = ('building', 'is_maintenance', 'requires_approval')
    
    # ช่องค้นหา
    search_fields = ('name', 'building')
    
    # *สำคัญ* ทำให้ติ๊กถูกแก้ไขค่าได้เลยจากหน้าตาราง (สะดวกมากสำหรับแอดมิน)
    list_editable = ('is_maintenance', 'requires_approval')


# -----------------------------------------------------------
# 2. ตั้งค่าการแสดงผล Booking (การจอง)
# -----------------------------------------------------------
class BookingAdmin(admin.ModelAdmin):
    # เพิ่ม 'get_equipments' เข้าไปในตารางแสดงผล
    list_display = ('title', 'room', 'user', 'start_time', 'end_time', 'status', 'get_equipments')
    
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'user__username', 'user__first_name', 'room__name')
    ordering = ('-start_time',)
    
    # แถบนำทางตามวันที่ (ด้านบนตาราง) ช่วยให้ค้นหาย้อนหลังง่าย
    date_hierarchy = 'start_time'
    
    # ฟังก์ชันดึงรายชื่ออุปกรณ์มาโชว์ (เพราะเป็น Many-to-Many Field)
    def get_equipments(self, obj):
        equipments = obj.equipments.all()
        if equipments:
            # ดึงชื่ออุปกรณ์มาต่อกันด้วยลูกน้ำ เช่น "ไมโครโฟน, ปลั๊กพ่วง"
            return ", ".join([e.name for e in equipments])
        return "-" # ถ้าไม่มีให้ขีดละไว้
    
    # ตั้งชื่อหัวข้อคอลัมน์ให้เป็นภาษาไทย
    get_equipments.short_description = "อุปกรณ์ที่ขอเพิ่มเติม"


# -----------------------------------------------------------
# 3. ตั้งค่า Audit Log (ประวัติการใช้งานระบบ)
# -----------------------------------------------------------
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'ip_address', 'timestamp')
    list_filter = ('action',)
    search_fields = ('user__username', 'details')
    readonly_fields = ('timestamp',) # ห้ามแก้ไขเวลา


# -----------------------------------------------------------
# 4. ลงทะเบียน Model ทั้งหมดเข้าสู่ระบบ Admin
# -----------------------------------------------------------
admin.site.register(Room, RoomAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
admin.site.register(OutlookToken)

# ลงทะเบียน Equipment (อุปกรณ์)
try:
    admin.site.register(Equipment)
except admin.sites.AlreadyRegistered:
    pass