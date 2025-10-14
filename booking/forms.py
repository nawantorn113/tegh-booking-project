# booking/forms.py
from django import forms
from .models import Booking, Profile # [สำคัญ] import Profile model เข้ามาด้วย
from django.utils import timezone
from datetime import time
from django.contrib.auth.forms import PasswordChangeForm # [สำคัญ] import ฟอร์มเปลี่ยนรหัสผ่าน

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'start_time', 'end_time', 
            'chairman', 'participant_count', 'department', 'requester_phone',
            'additional_notes'
        ]
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'chairman': forms.TextInput(attrs={'class': 'form-control'}),
            'participant_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'requester_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'เช่น ปากกาไวท์บอร์ด, สาย HDMI'}),
        }
        labels = {
            'title': 'วาระการประชุม',
            'chairman': 'ประธานการประชุม',
            'participant_count': 'จำนวนผู้เข้าร่วมประชุม',
            'requester_phone': 'เบอร์โทรติดต่อ',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time, end_time = cleaned_data.get("start_time"), cleaned_data.get("end_time")
        if start_time and end_time:
            if start_time < timezone.now(): raise forms.ValidationError("ไม่สามารถจองเวลาย้อนหลังได้")
            if end_time <= start_time: raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")
            if not (time(8, 0) <= start_time.time() and end_time.time() <= time(18, 0)): raise forms.ValidationError("สามารถเลือกเวลาจองได้ระหว่าง 08:00 น. ถึง 18:00 น. เท่านั้น")
            room = cleaned_data.get("room")
            conflicting = Booking.objects.filter(room=room, start_time__lt=end_time, end_time__gt=start_time).exclude(status='REJECTED')
            if self.instance.pk: conflicting = conflicting.exclude(pk=self.instance.pk)
            if conflicting.exists(): raise forms.ValidationError(f"ห้อง '{room.name}' ไม่ว่างในช่วงเวลานี้")
        return cleaned_data

# --- [ใหม่] เพิ่ม 2 Class นี้เข้าไป ---

# ฟอร์มสำหรับอัปโหลดรูป
class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture']
        labels = {
            'profile_picture': 'เปลี่ยนรูปโปรไฟล์ใหม่'
        }

# ฟอร์มสำหรับเปลี่ยนรหัสผ่าน
class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านเก่า'})
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านใหม่'})
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ยืนยันรหัสผ่านใหม่'})