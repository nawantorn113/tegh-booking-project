# booking/admin.py
from django.contrib import admin
from .models import Room, Booking, Profile

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity')
    search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room', 'start_time')
    search_fields = ('title', 'booked_by__username', 'room__name')
    list_editable = ('status',)
    date_hierarchy = 'start_time'

admin.site.register(Profile)