# booking/admin.py
from django.contrib import admin
from .models import Room, Booking, Profile

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity')
    list_filter = ('location',)
    search_fields = ('name', 'location')

# --- [อัปเกรด] ทำให้หน้าจัดการ Booking มีประสิทธิภาพมากขึ้น ---
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    # 1. แสดงคอลัมน์เหล่านี้ในตาราง
    list_display = ('title', 'room', 'booked_by', 'start_time', 'end_time', 'status')

    # 2. สร้างฟิลเตอร์ด้านข้างสำหรับกรองข้อมูล
    list_filter = ('status', 'room', 'booked_by__username')

    # 3. เพิ่มกล่องค้นหา
    search_fields = ('title', 'booked_by__username')

    # 4. (สำคัญที่สุด) ทำให้คอลัมน์ 'status' แก้ไขได้โดยตรงจากตาราง
    list_editable = ('status',)

admin.site.register(Profile)