# booking/models.py
from django.db import models
from django.contrib.auth.models import User

# ... (โค้ด Room model ยังคงเดิม) ...
class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อห้องประชุม")
    capacity = models.PositiveIntegerField(verbose_name="ความจุ (คน)")
    location = models.CharField(max_length=255, blank=True, verbose_name="ที่ตั้ง (อาคาร/ชั้น)")
    equipment = models.TextField(blank=True, verbose_name="รายการอุปกรณ์ (แต่ละรายการขึ้นบรรทัดใหม่)")

    def __str__(self):
        return self.name

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ถูกปฏิเสธ'),
    ]
    # [เพิ่ม] ตัวเลือกสำหรับการจองซ้ำ
    RECURRING_CHOICES = [
        ('NONE', 'ไม่มี'),
        ('DAILY', 'ทุกวัน'),
        ('WEEKLY', 'ทุกสัปดาห์'),
        ('MONTHLY', 'ทุกเดือน'),
    ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="ห้องประชุม")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้จอง")
    title = models.CharField(max_length=255, verbose_name="หัวข้อการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มต้น")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='APPROVED', verbose_name="สถานะ") # เปลี่ยน Default เป็น APPROVED เพื่อความง่าย
    created_at = models.DateTimeField(auto_now_add=True)
    # [เพิ่ม] field สำหรับการจองซ้ำ
    recurring = models.CharField(max_length=10, choices=RECURRING_CHOICES, default='NONE', verbose_name="การจองซ้ำ")

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name} โดย {self.booked_by.username}"

    class Meta:
        ordering = ['start_time']