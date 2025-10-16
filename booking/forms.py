# booking/forms.py
# [ฉบับแก้ไข AttributeError]

from django import forms
from django.contrib.auth.models import User
from dal import autocomplete
from .models import Room, Booking, Profile
from django.utils import timezone
from django.contrib.auth.forms import PasswordChangeForm

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'building', 'floor', 'location', 'capacity', 'equipment_in_room']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'equipment_in_room': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class BookingForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        # --- [แก้ไขครั้งสุดท้าย] เปลี่ยนชื่อ Widget ให้ถูกต้อง 100% ---
        widget=autocomplete.SelectMultiple(url='user-autocomplete'),
        required=False,
        label="รายชื่อผู้เข้าร่วม"
    )

    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'start_time', 'end_time', 
            'chairman', 'participant_count', 'participants', 
            'additional_notes', 'additional_requests',
            'attachment'
        ]
        widgets = {
            'room': forms.HiddenInput(),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'chairman': forms.TextInput(attrs={'class': 'form-control'}),
            'participant_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'additional_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'เช่น ขอ Whiteboard, ปากกา, หรือเครื่องดื่ม'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'วาระการประชุม',
            'chairman': 'ประธานการประชุม',
            'participant_count': 'จำนวนผู้เข้าร่วม (โดยประมาณ)',
            'additional_notes': 'หมายเหตุ',
            'additional_requests': 'คำขออุปกรณ์ / บริการเพิ่มเติม',
            'attachment': 'ไฟล์แนบประกอบการประชุม (ถ้ามี)',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time, end_time, room, participant_count = (
            cleaned_data.get("start_time"), cleaned_data.get("end_time"),
            cleaned_data.get("room"), cleaned_data.get("participant_count"),
        )
        if room and participant_count and participant_count > room.capacity:
            raise forms.ValidationError(f"จำนวนผู้เข้าร่วม ({participant_count}) เกินความจุของห้อง ({room.capacity})")
        if start_time and end_time:
            if self.instance.pk is None and start_time < timezone.now():
                raise forms.ValidationError("ไม่สามารถจองเวลาย้อนหลังได้")
            if end_time <= start_time:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")
            if room:
                conflicting = Booking.objects.filter(
                    room=room, start_time__lt=end_time, end_time__gt=start_time
                ).exclude(status__in=['REJECTED', 'CANCELLED'])
                if self.instance.pk:
                    conflicting = conflicting.exclude(pk=self.instance.pk)
                if conflicting.exists():
                    raise forms.ValidationError(f"ห้อง '{room.name}' ไม่ว่างในช่วงเวลานี้")
        return cleaned_data

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture', 'department']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = { 'profile_picture': 'เปลี่ยนรูปโปรไฟล์', 'department': 'แผนก' }

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านปัจจุบัน'})
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านใหม่'})
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ยืนยันรหัสผ่านใหม่'})