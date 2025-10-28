# booking/admin.py
from django.contrib import admin
# 1. ลบ Profile และ Equipment ออกจาก import นี้
from .models import Booking, Room, BookingFile, LoginHistory 

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'capacity')
    list_filter = ('building', 'floor')
    search_fields = ('name', 'building')

# 2. เพิ่ม Inline นี้สำหรับแสดงไฟล์ในหน้า Booking
class BookingFileInline(admin.TabularInline):
    model = BookingFile
    extra = 1 # จำนวนช่องอัปโหลดไฟล์ใหม่ที่จะแสดง

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room', 'start_time', 'booked_by__username')
    search_fields = ('title', 'booked_by__username', 'room__name')
    list_editable = ('status',)
    autocomplete_fields = ['participants', 'booked_by'] 
    inlines = [BookingFileInline] # 3. เพิ่ม Inline ที่นี่

# (ลบ EquipmentAdmin ออก)

# (ลบ ProfileAdmin ออก)

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp', 'user__username')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('user', 'action', 'timestamp', 'ip_address')

    def has_add_permission(self, request):
        return False 

    def has_change_permission(self, request, obj=None):
        return False