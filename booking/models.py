# booking/models.py
# [ฉบับสมบูรณ์ - มี Profile และ LoginHistory]

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อห้องประชุม")
    building = models.CharField(max_length=100, blank=True, null=True, verbose_name="อาคาร")
    floor = models.CharField(max_length=50, blank=True, null=True, verbose_name="ชั้น")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="โซน / สถานที่")
    capacity = models.PositiveIntegerField(verbose_name="ความจุ (คน)")
    equipment_in_room = models.TextField(blank=True, null=True, verbose_name="อุปกรณ์ที่มีในห้อง (แต่ละรายการขึ้นบรรทัดใหม่)")
    # --- Image Fields ---
    image1 = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพ 1")
    image2 = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพ 2")
    image3 = models.ImageField(upload_to='room_images/', blank=True, null=True, verbose_name="รูปภาพ 3")

    def __str__(self):
        return f"{self.name}{f' ({self.building})' if self.building else ''}"
    class Meta:
        verbose_name = "ห้องประชุม"
        verbose_name_plural = "ห้องประชุม"

class Booking(models.Model):
    STATUS_CHOICES = [('PENDING', 'รออนุมัติ'), ('APPROVED', 'อนุมัติแล้ว'), ('REJECTED', 'ถูกปฏิเสธ'), ('CANCELLED', 'ยกเลิกแล้ว')]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="ห้องประชุม")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้ขอใช้", related_name='bookings_made')
    title = models.CharField(max_length=255, verbose_name="หัวข้อการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มต้น")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    chairman = models.CharField(max_length=255, blank=True, null=True, verbose_name="ประธานการประชุม")
    participant_count = models.PositiveIntegerField(default=1, verbose_name="จำนวนผู้เข้าร่วม")
    participants = models.ManyToManyField(User, related_name='meetings_attending', blank=True, verbose_name="รายชื่อผู้เข้าร่วม")
    department_meeting = models.CharField(max_length=100, blank=True, null=True, verbose_name="แผนก (สำหรับการประชุม)")
    attachment = models.FileField(upload_to='booking_attachments/%Y/%m/', blank=True, null=True, verbose_name="ไฟล์เอกสาร")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="สถานะ")
    additional_notes = models.TextField(blank=True, null=True, verbose_name="หมายเหตุเพิ่มเติม")
    additional_requests = models.TextField(blank=True, null=True, verbose_name="คำขออุปกรณ์/บริการเพิ่มเติม")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="อัปเดตเมื่อ")

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name}"
    class Meta:
        ordering = ['-start_time']
        verbose_name = "การจอง"
        verbose_name_plural = "การจองทั้งหมด"

# --- [สำคัญ] คลาส Profile ที่หายไป ---
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="แผนก")

    def __str__(self):
        return f'Profile ของ {self.user.username}'
    class Meta:
        verbose_name = "โปรไฟล์ผู้ใช้"
        verbose_name_plural = "โปรไฟล์ผู้ใช้"
# --- --------------------------- ---

# --- [สำคัญ] คลาส LoginHistory ที่หายไป ---
class LoginHistory(models.Model):
    ACTION_CHOICES = [('LOGIN', 'เข้าสู่ระบบ'), ('LOGOUT', 'ออกจากระบบ')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    timestamp = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")

    def __str__(self):
        return f'{self.user.username} - {self.get_action_display()} at {self.timestamp}'
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "ประวัติการเข้าสู่ระบบ"
        verbose_name_plural = "ประวัติการเข้าสู่ระบบ"
# --- --------------------------------- ---

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
    try:
         if hasattr(instance, 'profile'):
             instance.profile.save()
         else:
             Profile.objects.create(user=instance)
    except Profile.DoesNotExist:
         Profile.objects.create(user=instance)
    except Exception as e:
         print(f"Error saving profile for user {instance.username}: {e}")