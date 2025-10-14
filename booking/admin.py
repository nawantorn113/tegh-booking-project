# booking/admin.py
from django.contrib import admin
from .models import Room, Booking, Profile # [แก้ไข] ไม่ต้อง import Equipment

# [ลบออก] ไม่ต้องมี EquipmentAdmin

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity')
    list_filter = ('location',)
    search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room', 'booked_by')
    search_fields = ('title', 'booked_by__username')
    list_editable = ('status',)
    # [ลบออก] ไม่ต้องมี filter_horizontal

admin.site.register(Profile)