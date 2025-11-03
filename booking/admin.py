from django.contrib import admin
# 1. (แก้ไข) ลบ 'LoginHistory' ออกจาก import นี้
from .models import Booking, Room

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'capacity')
    search_fields = ('name', 'building')
    list_filter = ('building', 'capacity')
    fieldsets = (
        (None, {
            'fields': ('name', 'building', 'floor', 'capacity', 'image')
        }),
        ('อุปกรณ์', {
            'fields': ('equipment_in_room',)
        }),
    )

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'user', 'start_time', 'end_time', 'status')
    search_fields = ('title', 'user__username', 'room__name', 'department')
    list_filter = ('status', 'room', 'start_time', 'department')
    autocomplete_fields = ['user', 'participants']
    list_editable = ('status',)
    list_per_page = 25
    
    fieldsets = (
        ('ข้อมูลหลัก', {
            'fields': ('title', 'room', 'user', 'department', 'status')
        }),
        ('วันและเวลา', {
            'fields': ('start_time', 'end_time')
        }),
        ('ผู้เข้าร่วม', {
            'fields': ('chairman', 'participant_count', 'participants')
        }),
        ('รายละเอียดเพิ่มเติม', {
            'fields': ('description', 'additional_requests', 'additional_notes', 'presentation_file')
        }),
    )

# 2. (แก้ไข) ลบบล็อกที่ลงทะเบียน 'LoginHistory' ทั้งหมดออกจากที่นี่
# (โค้ด @admin.register(LoginHistory) ... ถูกลบไปแล้ว)