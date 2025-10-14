from django.db import models
from django.contrib.auth.models import User

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อห้องประชุม")
    location = models.CharField(max_length=255, blank=True, verbose_name="อาคาร / สถานที่")
    capacity = models.PositiveIntegerField(verbose_name="ความจุ (คน)")
    equipment = models.TextField(blank=True, verbose_name="อุปกรณ์ที่พร้อมใช้งาน")

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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='APPROVED', verbose_name="สถานะ")

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name}"

    class Meta:
        ordering = ['start_time']