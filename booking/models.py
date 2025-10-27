# booking/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError # Import ValidationError
import os

# --- 1. 🟢 START: เพิ่ม Class Equipment (ที่หายไป) 🟢 ---
class Equipment(models.Model):
    name = models.CharField("ชื่ออุปกรณ์", max_length=100, unique=True)

    class Meta:
        verbose_name = "อุปกรณ์"
        verbose_name_plural = "อุปกรณ์"
        ordering = ['name']

    def __str__(self):
        return self.name
# --- 1. 🟢 END: เพิ่ม Class Equipment 🟢 ---


# --- 2. Model สำหรับห้อง ---
class Room(models.Model):
    name = models.CharField("ชื่อห้องประชุม", max_length=100, unique=True)
    capacity = models.PositiveIntegerField("ความจุ (คน)", default=1)
    building = models.CharField("อาคาร", max_length=50, blank=True, null=True)
    floor = models.CharField("ชั้น", max_length=20, blank=True, null=True)
    equipment_in_room = models.TextField("อุปกรณ์ภายในห้อง (อื่นๆ)", blank=True, null=True) # Field สำหรับพิมพ์อุปกรณ์อื่นๆ
    image = models.ImageField("รูปภาพห้องประชุม", upload_to='room_images/', blank=True, null=True)

    class Meta:
        verbose_name = "ห้องประชุม"
        verbose_name_plural = "ห้องประชุม"
        ordering = ['name']
    
    def __str__(self):
        return self.name

# --- 3. Model สำหรับการจอง ---
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
    
    # 1. สำหรับค้นหา (AD/User)
    participants = models.ManyToManyField(
        User, 
        verbose_name="ผู้เข้าร่วม (จาก AD/User)",
        related_name='participating_bookings', 
        blank=True
    )
    
    # 2. ✅ Field นี้ต้องมี (สำหรับพิมพ์ชื่อแขก) ✅
    external_participants = models.TextField(
        "รายชื่อผู้เข้าร่วม (ภายนอก)",
        blank=True, null=True,
        help_text="สำหรับแขก หรือผู้ที่ไม่มีบัญชีในระบบ (พิมพ์ชื่อ คั่นด้วยจุลภาค หรือขึ้นบรรทัดใหม่)"
    )

    # 3. สำหรับเลือกอุปกรณ์
    equipment = models.ManyToManyField(
        Equipment, 
        verbose_name="อุปกรณ์ที่ต้องการ",
        blank=True
    )
    
    # 4. สำหรับแนบไฟล์
    attachment = models.FileField(
        "ไฟล์แนบประกอบ", 
        upload_to='booking_attachments/%Y/%m/', 
        blank=True, null=True
    )
    
    status = models.CharField("สถานะ", max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # (Fields อื่นๆ ที่คุณอาจจะมี)
    chairman = models.CharField("ประธานในที่ประชุม", max_length=150, blank=True, null=True)
    department = models.CharField("แผนกผู้จอง", max_length=100, blank=True, null=True)
    description = models.TextField("รายละเอียด/วาระ", blank=True, null=True)
    presentation_file = models.FileField("ไฟล์นำเสนอ", upload_to='presentation_files/', blank=True, null=True)
    additional_requests = models.TextField("คำขอเพิ่มเติม", blank=True, null=True)
    additional_notes = models.TextField("หมายเหตุ", blank=True, null=True)


    class Meta:
        ordering = ['-start_time']
        verbose_name = "การจอง"
        verbose_name_plural = "รายการจองทั้งหมด"

    def __str__(self):
        return f"{self.title} ({self.room.name})"

    # --- ✅ ระบบตรวจสอบการจองซ้ำอัตโนมัติ ✅ ---
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

# (Model Profile และ LoginHistory ... ถ้ามี ก็ใส่ไว้ต่อจากนี้)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="ผู้ใช้")
    department = models.CharField("แผนก/ฝ่าย", max_length=100, blank=True, null=True)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=20, blank=True, null=True)
    avatar = models.ImageField("รูปโปรไฟล์", upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    def __str__(self):
        return f"Profile ของ {self.user.username}"

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