from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 

class Room(models.Model):
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100, blank=True, null=True)
    floor = models.CharField(max_length=50, blank=True, null=True)
    
    location = models.CharField(max_length=255, blank=True, null=True, help_text="เช่น 'ใกล้ฝ่ายบุคคล'")
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
    
    # --- 💡💡💡 [นี่คือจุดที่แก้ไข] 💡💡💡 ---
    is_active = models.BooleanField(
        default=True,
        help_text="ติ๊กออก เพื่อ 'ปิดปรับปรุง' ห้องนี้ (ห้องจะไม่แสดงในหน้าจอง)"
    )
    # --- 💡💡💡 [สิ้นสุดการแก้ไข] 💡💡💡 ---

    def __str__(self):
        return self.name

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