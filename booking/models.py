from django.db import models
from django.contrib.auth.models import User

class Room(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200, blank=True, null=True)
    capacity = models.IntegerField(default=10)

    def __str__(self):
        return self.name

class Booking(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # ใช้ user แทน booked_by
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'รออนุมัติ'),
        ('APPROVED', 'อนุมัติแล้ว'),
        ('REJECTED', 'ไม่อนุมัติ')
    ], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.room.name})"
