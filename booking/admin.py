# booking/admin.py
from django.contrib import admin
from .models import Room, Booking

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'location')
    search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    # [แก้ไข] เปลี่ยน 'user' เป็น 'booked_by'
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    
    # [แก้ไข] เปลี่ยน 'user' เป็น 'booked_by'
    list_filter = ('status', 'room', 'booked_by')
    
    # [แก้ไข] เปลี่ยน search field ให้ถูกต้อง
    search_fields = ('title', 'booked_by__username') 
    
    list_editable = ('status',)