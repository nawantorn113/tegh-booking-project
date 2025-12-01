from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 

# ----------------------------------------------------
#  [ใหม่] Model สำหรับเก็บ Access Token ของ Outlook
# ----------------------------------------------------
class OutlookToken(models.Model):
    """
    ใช้เก็บ OAuth Tokens สำหรับ Admin ที่เชื่อมต่อกับ Microsoft Graph API
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE) 
    access_token = models.TextField() # โทเค็นสำหรับ API Calls (หมดอายุเร็ว)
    refresh_token = models.TextField() # โทเค็นสำหรับขอ access_token ใหม่
    expires_at = models.DateTimeField() # วันหมดอายุของ Access Token
    
    def __str__(self):
        return f"Token for {self.user.username}"


class Room(models.Model):
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100, blank=True, null=True)
    floor = models.CharField(max_length=50, blank=True, null=True)
    
    location = models.CharField(max_length=255, blank=True, null=True, help_text="")
    capacity = models.PositiveIntegerField(default=1)
    equipment_in_room = models.TextField(blank=True, null=True, help_text="ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่")
    image = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพห้อง")

    approver = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approvable_rooms',
        help_text="เลือก User ที่มีสิทธิ์อนุมัติห้องนี้ (ถ้าเว้นว่าง = Admin กลาง)"
    )
    
    is_maintenance = models.BooleanField(
        default=False, 
        verbose_name="ปิดปรับปรุง (โหมดแมนนวล)",
    )
    
    maintenance_start = models.DateTimeField(
        null=True, blank=True,
        verbose_name="เริ่มปิดปรับปรุง (อัตโนมัติ)"
    )
    maintenance_end = models.DateTimeField(
        null=True, blank=True,
        verbose_name="สิ้นสุดปิดปรับปรุง (อัตโนมัติ)"
    )
    
    #  [เพิ่ม] ฟิลด์สำหรับ LINE/Teams
    line_notify_token = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="LINE Notify Token",
        help_text="โทเคนสำหรับแจ้งเตือนไปยังกลุ่ม LINE ประจำห้อง (ถ้ามี)"
    )
    teams_webhook_url = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Teams Webhook URL",
        help_text="URL สำหรับแจ้งเตือนไปยัง Channel Teams ประจำห้อง (ถ้ามี)"
    )
    
    @property
    def is_currently_under_maintenance(self):
        now = timezone.now()
        
        if self.is_maintenance and (not self.maintenance_start or not self.maintenance_end):
            return True
        
        if self.maintenance_start and self.maintenance_end:
            if self.maintenance_start <= now <= self.maintenance_end:
                return True
        
        return False

    def __str__(self):
        status = " (ปิดปรับปรุง)" if self.is_currently_under_maintenance else ""
        return f"{self.name}{status}"

    @property
    def equipment_list(self):
        if self.equipment_in_room:
            return [item.strip() for item in self.equipment_in_room.split('\n') if item.strip()]
        return []


class Booking(models.Model):
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    chairman = models.CharField(max_length=200, blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    participant_count = models.PositiveIntegerField(default=1)
    participants = models.ManyToManyField(User, related_name='participating_in', blank=True)
    presentation_file = models.FileField(upload_to='presentations/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    additional_requests = models.TextField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ไม่อนุมัติ'),
        ('CANCELLED', 'ยกเลิกแล้ว'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    parent_booking = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='child_bookings',
        help_text="การจองนี้ เป็นส่วนหนึ่งของการจองซ้ำ (ชี้ไปที่การจองแรก)"
    )
    recurrence_rule = models.CharField(max_length=20, blank=True, null=True)
    
    # [ใหม่] ฟิลด์สำหรับเก็บ ID ของ Event ที่สร้างใน Outlook
    outlook_event_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Outlook Event ID",
        help_text="ID ของ Event ที่ถูกสร้างใน Microsoft Calendar"
    )

    def __str__(self):
        return f"{self.title} - {self.room.name}"

    @property
    def is_past(self):
        if not self.end_time:
            return False
        return timezone.now() > self.end_time

    def can_user_edit_or_cancel(self, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        if self.is_past:
            return False
        return self.user == user

class AuditLog(models.Model):
    
    ACTION_CHOICES = [
        ('LOGIN', 'User Logged In'),
        ('BOOKING_CREATED', 'Booking Created'),
        ('BOOKING_EDITED', 'Booking Edited'),
        ('BOOKING_CANCELLED', 'Booking Cancelled'),
        ('BOOKING_APPROVED', 'Booking Approved'),
        ('BOOKING_REJECTED', 'Booking Rejected'),
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

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    line_user_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Profile: {self.user.username}"