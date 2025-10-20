# booking/admin.py
# [ฉบับเต็ม - เพิ่ม Field รูปภาพใน RoomAdmin]

from django.contrib import admin
from .models import Room, Booking, Profile, LoginHistory

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'capacity')
    search_fields = ('name', 'building', 'location')
    list_filter = ('building', 'capacity')
    # --- เพิ่ม Field รูปภาพใน Fieldsets ---
    fieldsets = (
        (None, {'fields': ('name', 'building', 'floor', 'location', 'capacity')}),
        ('อุปกรณ์', {'fields': ('equipment_in_room',)}),
        ('รูปภาพ (ถ้ามี)', {'fields': ('image1', 'image2', 'image3')}), # <-- เพิ่มส่วนนี้
    )
    # --- สิ้นสุดการเพิ่ม Field ---

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'booked_by__username', 'room__name')
    raw_id_fields = ('room', 'booked_by', 'participants')
    date_hierarchy = 'start_time'
    actions = ['approve_selected', 'reject_selected', 'cancel_selected']

    def approve_selected(self, request, queryset):
        rows_updated = queryset.update(status='APPROVED')
        self.message_user(request, f"{rows_updated} การจองได้รับการอนุมัติ")
    approve_selected.short_description = "อนุมัติการจองที่เลือก"

    def reject_selected(self, request, queryset):
        rows_updated = queryset.update(status='REJECTED')
        self.message_user(request, f"{rows_updated} การจองถูกปฏิเสธ")
    reject_selected.short_description = "ปฏิเสธการจองที่เลือก"

    def cancel_selected(self, request, queryset):
        rows_updated = queryset.update(status='CANCELLED')
        self.message_user(request, f"{rows_updated} การจองถูกยกเลิก")
    cancel_selected.short_description = "ยกเลิกการจองที่เลือก"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department')
    search_fields = ('user__username', 'department')
    raw_id_fields = ('user',) # Link to user

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'action', 'timestamp', 'ip_address')
    date_hierarchy = 'timestamp' # Add date filter

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False # Disable delete too