from django.contrib import admin
from .models import Booking, Room, Profile, LoginHistory

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'booked_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'room')
    search_fields = ('title', 'booked_by__username', 'room__name')
    ordering = ('-start_time',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'building', 'floor', 'capacity')
    search_fields = ('name', 'building')
    ordering = ('name',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'phone')


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action',)
    ordering = ('-timestamp',)
