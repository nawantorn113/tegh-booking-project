# booking/models.py
# [ฉบับมาสเตอร์]

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="ชื่อห้องประชุม")
    building = models.CharField(max_length=100, blank=True, verbose_name="อาคาร")
    floor = models.CharField(max_length=50, blank=True, verbose_name="ชั้น")
    location = models.CharField(max_length=255, blank=True, verbose_name="โซน / สถานที่")
    capacity = models.PositiveIntegerField(verbose_name="ความจุ (คน)")
    equipment_in_room = models.TextField(blank=True, verbose_name="อุปกรณ์ที่มีในห้อง (แต่ละรายการขึ้นบรรทัดใหม่)")

    def __str__(self):
        return f"{self.name} ({self.building})"

class Booking(models.Model):
    STATUS_CHOICES = [('PENDING', 'รออนุมัติ'), ('APPROVED', 'อนุมัติแล้ว'), ('REJECTED', 'ถูกปฏิเสธ'), ('CANCELLED', 'ยกเลิกแล้ว')]
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="ห้องประชุม")
    booked_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="ผู้ขอใช้")
    title = models.CharField(max_length=255, verbose_name="วาระการประชุม")
    start_time = models.DateTimeField(verbose_name="เวลาเริ่มต้น")
    end_time = models.DateTimeField(verbose_name="เวลาสิ้นสุด")
    chairman = models.CharField(max_length=255, blank=True, verbose_name="ประธานการประชุม")
    participant_count = models.PositiveIntegerField(default=1, verbose_name="จำนวนผู้เข้าร่วม (โดยประมาณ)")
    participants = models.ManyToManyField(User, related_name='meetings_attending', blank=True, verbose_name="รายชื่อผู้เข้าร่วม")
    additional_notes = models.TextField(blank=True, verbose_name="หมายเหตุ")
    additional_requests = models.TextField(blank=True, verbose_name="คำขออุปกรณ์ / บริการเพิ่มเติม")
    attachment = models.FileField(upload_to='attachments/%Y/%m/', blank=True, null=True, verbose_name="ไฟล์แนบ")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="สถานะ")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"'{self.title}' ในห้อง {self.room.name}"
    class Meta:
        ordering = ['-start_time']

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=100, blank=True, verbose_name="แผนก")
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg', verbose_name="รูปโปรไฟล์")

    def __str__(self):
        return f'{self.user.username} Profile'

class LoginHistory(models.Model):
    ACTION_CHOICES = [('LOGIN', 'เข้าสู่ระบบ'), ('LOGOUT', 'ออกจากระบบ')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    timestamp = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)

    def __str__(self):
        return f'{self.user.username} - {self.get_action_display()} at {self.timestamp}'
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "ประวัติการเข้าสู่ระบบ"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    if hasattr(instance, 'profile'):
        instance.profile.save()