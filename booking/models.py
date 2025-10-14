from django.db import models
from django.contrib.auth.models import User

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

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="ห้องประชุม")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้จอง")
    title = models.CharField(max_length=255, verbose_name="หัวข้อการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มต้น")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="สถานะ")
    recurring = models.BooleanField(default=False, verbose_name="จองซ้ำ")  # เพิ่มบรรทัดนี้
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name} โดย {self.booked_by.username}"

    class Meta:
        ordering = ['start_time']
