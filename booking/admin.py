from django.contrib import admin
from .models import Room, Booking

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity')
    list_filter = ('location',)
    search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room')
    search_fields = ('title', 'booked_by__username')