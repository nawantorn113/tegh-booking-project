from django.contrib import admin
from .models import Room, Booking, Equipment, Profile

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',); search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity'); list_filter = ('location',); search_fields = ('name', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status'); list_filter = ('status', 'room', 'booked_by'); search_fields = ('title', 'booked_by__username'); list_editable = ('status',); filter_horizontal = ('equipment_needed',)

admin.site.register(Profile)