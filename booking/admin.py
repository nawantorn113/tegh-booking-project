# booking/admin.py
# [ฉบับสมบูรณ์]

from django.contrib import admin
from .models import Room, Booking, Profile, LoginHistory

admin.site.register(Room)
admin.site.register(Booking)
admin.site.register(Profile)
admin.site.register(LoginHistory)