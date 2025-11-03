from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 

class Room(models.Model):
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100, blank=True, null=True)
    floor = models.CharField(max_length=50, blank=True, null=True)
    
    # (ฟิลด์ที่เราเพิ่มเข้ามาสำหรับหน้า UI ใหม่)
    location = models.CharField(max_length=255, blank=True, null=True, help_text="เช่น 'ใกล้ฝ่ายบุคคล'")
    capacity = models.PositiveIntegerField(default=1)
    equipment_in_room = models.TextField(blank=True, null=True, help_text="ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่")
    
    # (ใช้ 'image' รูปเดียวตามที่เราแก้ไขล่าสุด)
    image = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพห้อง")

    def __str__(self):
        return self.name

    @property
    def equipment_list(self):
        """
        แปลง Text 'equipment_in_room' (ที่มีหลายบรรทัด)
        ให้กลายเป็น List (สำหรับ Template ที่ต้องการวนลูป)
        """
        if self.equipment_in_room:
            return [item.strip() for item in self.equipment_in_room.split('\n') if item.strip()]
        return []

class Booking(models.Model):
    # (ฟิลด์ที่เชื่อมโยง)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    
    # (รายละเอียดการประชุม)
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # (ข้อมูลเพิ่มเติม)
    chairman = models.CharField(max_length=200, blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    participant_count = models.PositiveIntegerField(default=1)
    participants = models.ManyToManyField(User, related_name='participating_in', blank=True)
    presentation_file = models.FileField(upload_to='presentations/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    additional_requests = models.TextField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    
    # (สถานะ)
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ไม่อนุมัติ'),
        ('CANCELLED', 'ยกเลิกแล้ว'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.room.name}"

    @property
    def is_past(self):
        """
        ตรวจสอบว่า "การประชุมนี้จบไปหรือยัง" (นับที่เวลาสิ้นสุด)
        """
        if not self.end_time:
            return False
        return timezone.now() > self.end_time

    def can_user_edit_or_cancel(self, user):
        """
        ตรวจสอบสิทธิ์ ว่า User คนนี้ (ที่ login) แก้ไข/ยกเลิก ได้หรือไม่
        """
        if not user or not user.is_authenticated:
            return False
            
        # 1. Admin (is_staff) ทำได้ทุกอย่าง
        if user.is_staff:
            return True
        
        # 2. ถ้าประชุมจบไปแล้ว (is_past) = ห้ามทำอะไรทั้งสิ้น
        if self.is_past:
            return False
            
        # 3. ถ้ายังไม่จบ ต้องเป็น "เจ้าของ" การจองเท่านั้น
        return self.user == user