# booking/forms.py
from django import forms
from .models import Booking, Equipment # ตรวจสอบว่า import Equipment มาด้วย
from django.utils import timezone
from datetime import time

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        # [แก้ไข] ตรวจสอบให้แน่ใจว่า 'equipment_needed' อยู่ใน list นี้
        fields = [
            'room', 'title', 'start_time', 'end_time', 
            'chairman', 'participant_count', 'department', 'requester_phone',
            'equipment_needed', 'additional_notes'
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
            'equipment_needed': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}), # กำหนดให้เป็น Checkbox
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'title': 'วาระการประชุม',
            'chairman': 'ประธานการประชุม',
            'participant_count': 'จำนวนผู้เข้าร่วมประชุม',
            'requester_phone': 'เบอร์โทรติดต่อ',
            'equipment_needed': 'เลือกอุปกรณ์เสริมที่ต้องการ', # เพิ่ม Label
            'additional_notes': 'รายละเอียดเพิ่มเติม',
        }

    def clean(self):
        # ... โค้ดส่วน clean() ไม่ต้องแก้ไข ...
        # (ตรวจสอบให้แน่ใจว่ามีอยู่ครบถ้วน)
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:
            if start_time < timezone.now():
                raise forms.ValidationError("ไม่สามารถจองเวลาย้อนหลังได้")
            if end_time <= start_time:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")

            allowed_start_time = time(8, 0)
            allowed_end_time = time(18, 0)
            if not (allowed_start_time <= start_time.time() and end_time.time() <= allowed_end_time):
                raise forms.ValidationError("สามารถเลือกเวลาจองได้ระหว่าง 08:00 น. ถึง 18:00 น. เท่านั้น")

            room = cleaned_data.get("room")
            conflicting_bookings = Booking.objects.filter(
                room=room, start_time__lt=end_time, end_time__gt=start_time,
            ).exclude(status='REJECTED')
            if self.instance.pk:
                conflicting_bookings = conflicting_bookings.exclude(pk=self.instance.pk)
            if conflicting_bookings.exists():
                raise forms.ValidationError(f"ห้อง '{room.name}' ไม่ว่างในช่วงเวลานี้")
        return cleaned_data

# ... โค้ด ProfilePictureForm และ CustomPasswordChangeForm ...