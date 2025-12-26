from django.contrib import admin
from .models import Room, Booking, Equipment, UserProfile, AuditLog

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    # ลบ 'requires_approval' ออกจากรายการ
    list_display = ('name', 'capacity', 'location', 'floor', 'building', 'is_active', 'is_maintenance', 'approver')
    list_filter = ('is_active', 'is_maintenance', 'building', 'floor')
    search_fields = ('name', 'location', 'description')
    list_editable = ('is_active', 'is_maintenance', 'approver') # แก้ไขสถานะและผู้อนุมัติได้เลยจากหน้าตาราง

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'user', 'start_time', 'end_time', 'status', 'department')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'user__username', 'user__first_name', 'department')
    date_hierarchy = 'start_time'
    
    # แสดงฟิลด์แบบ Readonly ในหน้าดูรายละเอียด (บางส่วน)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'phone', 'line_user_id')
    search_fields = ('user__username', 'user__first_name', 'department')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'details', 'ip_address')
    readonly_fields = ('timestamp', 'user', 'action', 'details', 'ip_address')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False