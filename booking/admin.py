from django.contrib import admin
from .models import Room, Booking

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'capacity']
    search_fields = ['name', 'location']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['title', 'room', 'user', 'start_time', 'end_time', 'status']  # ใช้ user แทน booked_by
    list_filter = ['room', 'status', 'user']  # ใช้ user แทน booked_by
    search_fields = ['title', 'room__name', 'user__username']
