# booking/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django import forms

class Room(models.Model):
    name = models.CharField("ชื่อห้องประชุม", max_length=100, unique=True)
    building = models.CharField("อาคาร", max_length=50, blank=True, null=True)
    floor = models.CharField("ชั้น", max_length=20, blank=True, null=True)
    capacity = models.PositiveIntegerField("ความจุ (คน)", default=1)
    equipment_in_room = models.TextField(
        "อุปกรณ์ภายในห้อง",
        blank=True, null=True,
        help_text="ระบุอุปกรณ์ทีละรายการ บรรทัดละอย่าง"
    )
    image = models.ImageField(
        "รูปภาพห้องประชุม",
        upload_to='room_images/',
        blank=True, null=True
    )

    class Meta:
        ordering = ['building', 'floor', 'name']
        verbose_name = "ห้องประชุม"
        verbose_name_plural = "ห้องประชุม"

    def __str__(self):
        return self.name

class Booking(models.Model):
    room = models.ForeignKey(Room, verbose_name="ห้องประชุม", on_delete=models.CASCADE, related_name='bookings')
    booked_by = models.ForeignKey(User, verbose_name="ผู้จอง", on_delete=models.CASCADE, related_name='booking')
    title = models.CharField("หัวข้อการประชุม", max_length=200)
    description = models.TextField("รายละเอียด/วาระ", blank=True, null=True)
    start_time = models.DateTimeField("เวลาเริ่มต้น", default=timezone.now)
    end_time = models.DateTimeField("เวลาสิ้นสุด", default=timezone.now)
    participant_count = models.PositiveIntegerField("จำนวนผู้เข้าร่วม (โดยประมาณ)", default=1)
    participants = models.ManyToManyField(
        User,
        verbose_name="รายชื่อผู้เข้าร่วม (ในระบบ)", # <-- เปลี่ยนชื่อเล็กน้อย
        related_name='participating_bookings',
        blank=True
    )

    # --- 🟢 เพิ่ม Field นี้ 🟢 ---
    external_participants = models.TextField(
        "รายชื่อผู้เข้าร่วม (ภายนอก)",
        blank=True, null=True,
        help_text="สำหรับแขก หรือผู้ที่ไม่มีบัญชีในระบบ (พิมพ์ชื่อ คั่นด้วยจุลภาค หรือขึ้นบรรทัดใหม่)"
    )
    # --- --------------------- ---

    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'), ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ถูกปฏิเสธ'), ('CANCELLED', 'ยกเลิกแล้ว'),
    ]
    status = models.CharField("สถานะ", max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    chairman = models.CharField("ประธานในที่ประชุม", max_length=150, blank=True, null=True)
    department = models.CharField("แผนกผู้จอง", max_length=100, blank=True, null=True)
    presentation_file = models.FileField("ไฟล์นำเสนอ", upload_to='presentation_files/', blank=True, null=True, help_text="ไฟล์ที่ต้องการเปิดขึ้นจอ (PDF, PPT, Word, Excel)")
    additional_requests = models.TextField("คำขอเพิ่มเติม", blank=True, null=True, help_text="เช่น กาแฟ, อุปกรณ์พิเศษ")
    attachment = models.FileField("ไฟล์แนบอื่นๆ", upload_to='booking_attachments/', blank=True, null=True, help_text="เอกสารอื่นๆ ที่เกี่ยวข้อง")
    additional_notes = models.TextField("หมายเหตุ", blank=True, null=True)

    class Meta:
        ordering = ['-start_time']
        verbose_name = "การจอง"
        verbose_name_plural = "รายการจองทั้งหมด"

    def __str__(self):
        start_str = self.start_time.strftime('%d/%m/%y %H:%M') if self.start_time else "N/A"
        room_name = self.room.name if hasattr(self, 'room') and self.room else "N/A"
        return f"{self.title} ({room_name}) - {start_str}"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise forms.ValidationError({'end_time': 'เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น'})
        check_conflict = False
        if self.pk is None: check_conflict = True
        else:
            if hasattr(self, '_Booking__original_start_time') and self.start_time != self.__original_start_time: check_conflict = True
            if hasattr(self, '_Booking__original_end_time') and self.end_time != self.__original_end_time: check_conflict = True
            if hasattr(self, '_Booking__original_room') and self.room != self.__original_room: check_conflict = True
        if check_conflict and self.room and self.start_time and self.end_time:
            conflicts = Booking.objects.filter(
                room=self.room, start_time__lt=self.end_time, end_time__gt=self.start_time
            ).exclude(pk=self.pk).exclude(status__in=['REJECTED', 'CANCELLED'])
            if conflicts.exists():
                conflict_details = conflicts.first()
                start_h = conflict_details.start_time.strftime("%H:%M") if conflict_details.start_time else "N/A"
                end_h = conflict_details.end_time.strftime("%H:%M") if conflict_details.end_time else "N/A"
                raise forms.ValidationError(
                    f'ห้อง "{self.room.name}" ไม่ว่างในช่วงเวลานี้ '
                    f'เนื่องจากมีการจอง "{conflict_details.title}" '
                    f'เวลา {start_h} - {end_h} อยู่แล้ว'
                )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.pk:
            self.__original_start_time = self.start_time
            self.__original_end_time = self.end_time
            self.__original_room = self.room
        else:
            self.__original_start_time = None
            self.__original_end_time = None
            initial_room_id = kwargs.get('initial', {}).get('room') if 'initial' in kwargs else None
            self.__original_room = Room.objects.get(pk=initial_room_id) if initial_room_id else None


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="ผู้ใช้")
    department = models.CharField("แผนก/ฝ่าย", max_length=100, blank=True, null=True)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=20, blank=True, null=True)
    avatar = models.ImageField("รูปโปรไฟล์", upload_to='avatars/', default='avatars/default.png', blank=True, null=True)
    class Meta:
        verbose_name = "ข้อมูลผู้ใช้เพิ่มเติม"
        verbose_name_plural = "ข้อมูลผู้ใช้เพิ่มเติม"
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
        verbose_name = "ประวัติการเข้าใช้งาน"
        verbose_name_plural = "ประวัติการเข้าใช้งาน"
    def __str__(self):
        action_display = dict(self.ACTION_CHOICES).get(self.action, self.action)
        time_display = self.timestamp.strftime('%Y-%m-%d %H:%M') if self.timestamp else "N/A"
        return f"{self.user.username} - {action_display} at {time_display}"