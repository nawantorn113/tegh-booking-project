from django.contrib import admin
from .models import Room, Booking, AuditLog # 1. (เพิ่ม AuditLog)

# --- 💡💡💡 [นี่คือจุดที่แก้ไข] 💡💡💡 ---
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    ตั้งค่าการแสดงผล Audit Log ในหน้า Admin
    """
    list_display = ('timestamp', 'user', 'action', 'ip_address', 'details')
    list_filter = ('action', 'user')
    search_fields = ('user__username', 'details', 'ip_address')
    
    # (ตั้งค่าให้ "อ่านได้อย่างเดียว" ห้ามแก้ไข)
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
# --- 💡💡💡 [สิ้นสุดการแก้ไข] 💡💡💡 ---


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'capacity')
    list_filter = ('building', 'capacity')
    search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'user', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'user__username', 'room__name')
    
    # (เพิ่มฟังก์ชันนี้เพื่อให้แสดง m2m (participants) ได้ ถ้าต้องการ)
    # filter_horizontal = ('participants',)