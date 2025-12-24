from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 

# ----------------------------------------------------
# 1. Model สำหรับเก็บ Access Token ของ Outlook
# ----------------------------------------------------
class OutlookToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='outlook_token') 
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"Token for {self.user.username}"

# ----------------------------------------------------
# 2. Model สำหรับอุปกรณ์ (Equipment)
# ----------------------------------------------------
class Equipment(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่ออุปกรณ์")
    description = models.TextField(blank=True, null=True, verbose_name="รายละเอียด")
    
    def __str__(self):
        return self.name

# ----------------------------------------------------
# 3. Model ห้องประชุม
# ----------------------------------------------------
class Room(models.Model):
    name = models.CharField(max_length=100, verbose_name="ชื่อห้องประชุม")
    building = models.CharField(max_length=100, blank=True, null=True, verbose_name="อาคาร/ตึก")
    floor = models.CharField(max_length=50, blank=True, null=True, verbose_name="ชั้น")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="สถานที่ตั้ง")
    capacity = models.PositiveIntegerField(default=1, verbose_name="ความจุ (คน)")
    
    equipment_in_room = models.TextField(blank=True, null=True, help_text="ระบุอุปกรณ์ถาวรในห้อง", verbose_name="อุปกรณ์ถาวรในห้อง")
    image = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพห้อง")

    # [สำคัญ] ผู้อนุมัติห้อง (Approver)
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approver_rooms', verbose_name="ผู้อนุมัติ")
    
    is_maintenance = models.BooleanField(default=False, verbose_name="สถานะปิดปรับปรุง")
    maintenance_start = models.DateTimeField(null=True, blank=True, verbose_name="เริ่มปิดปรับปรุง")
    maintenance_end = models.DateTimeField(null=True, blank=True, verbose_name="สิ้นสุดปิดปรับปรุง")
    
    requires_approval = models.BooleanField(default=True, verbose_name="ต้องรออนุมัติ")
    
    line_notify_token = models.CharField(max_length=50, blank=True, null=True, verbose_name="Line Notify Token")
    teams_webhook_url = models.TextField(blank=True, null=True, verbose_name="Teams Webhook URL")
    
    @property
    def is_currently_under_maintenance(self):
        now = timezone.now()
        if self.is_maintenance:
            if not self.maintenance_start or not self.maintenance_end:
                return True
            if self.maintenance_start <= now <= self.maintenance_end:
                return True
        return False

    def __str__(self):
        status = " (ปิดปรับปรุง)" if self.is_currently_under_maintenance else ""
        return f"{self.name}{status}"

# ----------------------------------------------------
# 4. Model การจอง (Booking)
# ----------------------------------------------------
class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    
    title = models.CharField(max_length=200, verbose_name="หัวข้อการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่ม")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    
    chairman = models.CharField(max_length=200, blank=True, null=True, verbose_name="ประธาน")
    department = models.CharField(max_length=200, blank=True, null=True, verbose_name="แผนก")
    participant_count = models.PositiveIntegerField(default=1, verbose_name="จำนวนคน")
    
    participants = models.ManyToManyField(User, related_name='participating_in', blank=True, verbose_name="ผู้เข้าร่วม")

    is_user_seen = models.BooleanField(default=False, verbose_name="ผู้จองรับทราบแล้ว")
    
    equipments = models.ManyToManyField(Equipment, blank=True, related_name='bookings', verbose_name="อุปกรณ์ที่ขอเพิ่ม")

    presentation_file = models.FileField(upload_to='presentations/', blank=True, null=True, verbose_name="ไฟล์นำเสนอ")
    description = models.TextField(blank=True, null=True, verbose_name="รายละเอียด")
    additional_requests = models.TextField(blank=True, null=True, verbose_name="คำขอเพิ่มเติม")
    additional_notes = models.TextField(blank=True, null=True, verbose_name="หมายเหตุ")
    
    LAYOUT_CHOICES = (
        ('theatre', 'Theatre (เธียเตอร์)'),
        ('classroom', 'Classroom (แบบห้องเรียน)'),
        ('u_shape', 'U-Shape (รูปตัว U)'),
        ('banquet', 'Banquet (แบบจัดเลี้ยง)'),
        ('banquet_rounds', 'Banquet Rounds (โต๊ะจีน)'),
        ('conference', 'Conference (ห้องประชุมยาว)'),
        ('other', 'อื่นๆ (ระบุเพิ่มเติม)'),
    )

    room_layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default='theatre',
        verbose_name="รูปแบบการจัดห้อง"
    )
    
    room_layout_attachment = models.FileField(
        upload_to='layout_attachments/', 
        blank=True, 
        null=True, 
        verbose_name="ไฟล์แนบผังห้อง"
    )
    
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ไม่อนุมัติ'),
        ('CANCELLED', 'ยกเลิกแล้ว'),  # ต้องมีอันนี้ด้วย ไม่งั้นระบบยกเลิกจะ Error
    ]
    
    # [จุดสำคัญ] บังคับ Default เป็น PENDING เพื่อให้ทุกการจองต้องรออนุมัติ
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    parent_booking = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_bookings')
    recurrence_rule = models.CharField(max_length=20, blank=True, null=True)
    
    outlook_event_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.room.name}"

    @property
    def is_past(self):
        if not self.end_time: return False
        return timezone.now() > self.end_time

    def can_user_edit_or_cancel(self, user):
        if not user or not user.is_authenticated: return False
        if user.is_staff: return True
        if self.is_past: return False
        return self.user == user

# ----------------------------------------------------
# 5. Model ประวัติการใช้งาน (Audit Log)
# ----------------------------------------------------
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'User Logged In'),
        ('BOOKING_CREATED', 'Booking Created'),
        ('BOOKING_EDITED', 'Booking Edited'),
        ('BOOKING_CANCELLED', 'Booking Cancelled'),
        ('BOOKING_APPROVED', 'Booking Approved'),
        ('BOOKING_REJECTED', 'Booking Rejected'),
        ('OUTLOOK_SYNC', 'Outlook Synced'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.user} - {self.get_action_display()}"

    class Meta:
        ordering = ['-timestamp']

# ----------------------------------------------------
# 6. Model ข้อมูลเสริมผู้ใช้ (UserProfile)
# ----------------------------------------------------
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="แผนก")
    line_user_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        dept_str = f" ({self.department})" if self.department else ""
        return f"{self.user.username}{dept_str}"