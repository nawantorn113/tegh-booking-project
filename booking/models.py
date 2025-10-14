# booking/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# [ใหม่] Model สำหรับเก็บรายการอุปกรณ์ทั้งหมด
class Equipment(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่ออุปกรณ์")

    def __str__(self):
        return self.name

# booking/models.py

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อห้องประชุม")
    location = models.CharField(max_length=255, blank=True, verbose_name="อาคาร / สถานที่")
    capacity = models.PositiveIntegerField(verbose_name="ความจุ (คน)")
    # [แก้ไข] เปลี่ยนชื่อ field เพื่อความชัดเจน
    equipment_in_room = models.TextField(blank=True, verbose_name="อุปกรณ์ที่พร้อมใช้งาน")

    def __str__(self):
        return f"{self.name} ({self.location})"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ถูกปฏิเสธ'),
    ]

    # --- ข้อมูลหลัก ---
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="ห้องประชุม")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้ขอใช้")
    title = models.CharField(max_length=255, verbose_name="วาระการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มต้น")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    
    # --- [แก้ไข] เพิ่มรายละเอียดการจองทั้งหมด ---
    chairman = models.CharField(max_length=255, blank=True, verbose_name="ประธานการประชุม")
    participant_count = models.PositiveIntegerField(default=1, verbose_name="จำนวนผู้เข้าร่วม")
    department = models.CharField(max_length=255, blank=True, verbose_name="แผนก")
    requester_phone = models.CharField(max_length=20, blank=True, verbose_name="เบอร์โทรติดต่อ")
    equipment_needed = models.ManyToManyField(Equipment, blank=True, verbose_name="อุปกรณ์ที่ต้องใช้")
    additional_notes = models.TextField(blank=True, verbose_name="เพิ่มเติม")

    # --- ข้อมูลระบบ ---
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="สถานะ")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name}"

    class Meta:
        ordering = ['-start_time']

# [ใหม่] Model สำหรับเก็บโปรไฟล์ผู้ใช้
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg', verbose_name="รูปโปรไฟล์")

    def __str__(self):
        return f'{self.user.username} Profile'

# [ใหม่] สร้าง Profile อัตโนมัติเมื่อมี User ใหม่ถูกสร้างขึ้น
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        # If profile doesn't exist, create it.
        Profile.objects.create(user=instance)