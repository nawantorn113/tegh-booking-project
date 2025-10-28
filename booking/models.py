# booking/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import os

# (ลบ Class Equipment)

class Room(models.Model):
    name = models.CharField("ชื่อห้องประชุม", max_length=100, unique=True)
    capacity = models.PositiveIntegerField("ความจุ (คน)", default=1)
    building = models.CharField("อาคาร", max_length=50, blank=True, null=True)
    floor = models.CharField("ชั้น", max_length=20, blank=True, null=True)
    equipment_in_room = models.TextField("อุปกรณ์ภายในห้อง (อื่นๆ)", blank=True, null=True, help_text="อุปกรณ์ที่มีให้ในห้อง (เช่น โปรเจคเตอร์, ไวท์บอร์ด)")
    image = models.ImageField("รูปภาพห้องประชุม", upload_to='room_images/', blank=True, null=True)

    class Meta:
        verbose_name = "ห้องประชุม"
        verbose_name_plural = "ห้องประชุม"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'), ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ถูกปฏิเสธ'), ('CANCELLED', 'ยกเลิกแล้ว'),
    ]

    room = models.ForeignKey(Room, verbose_name="ห้องประชุม", on_delete=models.CASCADE, related_name='bookings')
    booked_by = models.ForeignKey(User, verbose_name="ผู้จอง", on_delete=models.CASCADE, related_name='bookings_made')
    title = models.CharField("หัวข้อการประชุม", max_length=200)
    start_time = models.DateTimeField("เวลาเริ่มต้น", default=timezone.now)
    end_time = models.DateTimeField("เวลาสิ้นสุด", default=timezone.now)
    
    participant_count = models.PositiveIntegerField("จำนวนผู้เข้าร่วม (ตัวเลข)", default=1)
    
    participants = models.ManyToManyField(
        User, 
        verbose_name="ผู้เข้าร่วม (จาก AD/User)",
        related_name='participating_bookings', 
        blank=True
    )
    
    # (ลบ external_participants ออก)
    # (ลบ equipment (m2m) ออก)
    
    status = models.CharField("สถานะ", max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    chairman = models.CharField("ประธานในที่ประชุม", max_length=150, blank=True, null=True)
    department = models.CharField("แผนกผู้จอง", max_length=100, blank=True, null=True)
    description = models.TextField("รายละเอียด/วาระ", blank=True, null=True)
    
    # (นี่คือ Field ที่ผู้ใช้จะพิมพ์เอง)
    additional_requests = models.TextField("คำขอเพิ่มเติม (เช่น กาแฟ, อุปกรณ์พิเศษ)", blank=True, null=True)
    
    additional_notes = models.TextField("หมายเหตุ", blank=True, null=True)


    class Meta:
        ordering = ['-start_time']
        verbose_name = "การจอง"
        verbose_name_plural = "รายการจองทั้งหมด"

    def __str__(self):
        return f"{self.title} ({self.room.name})"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น'})
        
        if self.room and self.start_time and self.end_time:
            conflicts = Booking.objects.filter(
                room=self.room,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(
                status__in=['REJECTED', 'CANCELLED']
            )
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError(
                    f'ห้อง "{self.room.name}" ไม่ว่างในช่วงเวลานี้แล้ว'
                )

# --- เพิ่ม Model ใหม่สำหรับเก็บไฟล์ (รองรับหลายไฟล์) ---
def get_booking_upload_path(instance, filename):
    return f'booking_files/booking_{instance.booking.id}/{filename}'

class BookingFile(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='files')
    file = models.FileField("ไฟล์", upload_to=get_booking_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking.title} - {os.path.basename(self.file.name)}"
# --- -------------------------------------------------- ---


# --- (ลบ Model Profile ทั้งหมด) ---

class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้ใช้")
    timestamp = models.DateTimeField("เวลาที่บันทึก", auto_now_add=True)
    ACTION_CHOICES = [('LOGIN', 'เข้าสู่ระบบ'), ('LOGOUT', 'ออกจากระบบ')]
    action = models.CharField("การกระทำ", max_length=10, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField("IP Address", null=True, blank=True)
    class Meta:
        ordering = ['-timestamp']
    def __str__(self):
        return f"{self.user.username} - {dict(self.ACTION_CHOICES).get(self.action)} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"