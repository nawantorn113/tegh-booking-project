from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# 1. Room Model
class Room(models.Model):
    name = models.CharField(max_length=100)
    capacity = models.IntegerField(default=10)
    equipment_in_room = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='room_images/', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    floor = models.CharField(max_length=50, blank=True, null=True)
    building = models.CharField(max_length=100, blank=True, null=True)
    
    is_maintenance = models.BooleanField(default=False, verbose_name="ปิดปรับปรุง (Manual)")
    maintenance_start = models.DateTimeField(null=True, blank=True)
    maintenance_end = models.DateTimeField(null=True, blank=True)
    
    status_note = models.CharField(max_length=255, blank=True, null=True, verbose_name="หมายเหตุสถานะ")
    
    description = models.TextField(blank=True, null=True)
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rooms_to_approve')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def is_currently_under_maintenance(self):
        if self.is_maintenance:
            return True
        if self.maintenance_start and self.maintenance_end:
            now = timezone.now()
            return self.maintenance_start <= now <= self.maintenance_end
        return False

# 2. Equipment Model
class Equipment(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="สถานะพร้อมใช้งาน")
    status_note = models.CharField(max_length=255, blank=True, null=True, verbose_name="หมายเหตุสถานะ")
    
    def __str__(self):
        return self.name

# 3. Booking Model
class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ไม่อนุมัติ'),
        ('CANCELLED', 'ยกเลิก'),
    ]
    
    # [เพิ่มใหม่] ประเภทการจอง
    BOOKING_TYPE_CHOICES = [
        ('general', 'ประชุมทั่วไป'),
        ('cleaning', 'แม่บ้านทำความสะอาด'),
    ]
    
    LAYOUT_CHOICES = [
        ('theatre', 'แบบเธียร์เตอร์ (Theatre)'),
        ('classroom', 'แบบห้องเรียน (Classroom)'),
        ('u_shape', 'แบบตัวยู (U-Shape)'),
        ('boardroom', 'แบบห้องประชุม (Conference)'),
        ('banquet', 'แบบจัดเลี้ยง (Banquet)'),
        ('banquet_rounds', 'แบบจัดเลี้ยงโต๊ะกลม (Banquet Rounds)'),
        ('other', 'อื่นๆ (ระบุในไฟล์แนบ)'),
    ]

    title = models.CharField(max_length=200)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # [เพิ่มใหม่] Field เก็บประเภทการจอง
    booking_type = models.CharField(
        max_length=20, 
        choices=BOOKING_TYPE_CHOICES, 
        default='general', 
        verbose_name="ประเภทการจอง"
    )
    
    participant_count = models.IntegerField(default=1)
    department = models.CharField(max_length=100, blank=True, null=True)
    chairman = models.CharField(max_length=100, blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    additional_requests = models.TextField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    
    room_layout = models.CharField(max_length=50, choices=LAYOUT_CHOICES, default='theatre', blank=True)
    room_layout_attachment = models.FileField(upload_to='layouts/', blank=True, null=True)
    
    presentation_file = models.FileField(upload_to='presentations/', blank=True, null=True)
    presentation_link = models.URLField(max_length=500, blank=True, null=True, verbose_name="ลิงก์เอกสารประกอบ")
    
    equipments = models.ManyToManyField(Equipment, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approver_comment = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    outlook_event_id = models.CharField(max_length=255, blank=True, null=True)
    is_user_seen = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} - {self.room.name}"
        
    def can_user_edit_or_cancel(self, user):
        if timezone.now() > self.end_time:
            return False
        if self.status in ['CANCELLED', 'REJECTED']:
            return False
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            return True
        if self.user == user:
            return True
        return False

# 4. User Profile & Signals
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="แผนก")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="เบอร์โทรศัพท์")
    line_user_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Line User ID")

    def __str__(self):
        return f"Profile of {self.user.username}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

# 5. Logs & Tokens
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class OutlookToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField()