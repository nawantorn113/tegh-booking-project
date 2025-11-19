from django.contrib import admin
from .models import Room, Booking, AuditLog, OutlookToken

# 1. ตั้งค่าการแสดงผล Booking
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'room', 'user', 'start_time', 'end_time', 'status', 'participant_count')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'user__username', 'user__first_name')
    ordering = ('-start_time',)

# 2. ตั้งค่าการแสดงผล Room
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor', 'capacity', 'is_maintenance')
    list_filter = ('building', 'is_maintenance')
    search_fields = ('name',)

# 3. ลงทะเบียน Model
admin.site.register(Room, RoomAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(AuditLog)
admin.site.register(OutlookToken)