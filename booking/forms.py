# booking/forms.py
# [ฉบับสมบูรณ์ - ไม่มีรูปภาพ, ไม่มี ProfileForm]

from django import forms
from django.contrib.auth.models import User
from .models import Room, Booking, Profile # Profile ยังคงต้อง import อยู่
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.core.exceptions import ValidationError

# --- try...except สำหรับ dal_select2 ---
try:
    from dal import autocomplete
    DAL_AVAILABLE = True
except ImportError:
    print("WARNING: dal_select2 (django-autocomplete-light) not installed. Participant autocomplete will not work.")
    DAL_AVAILABLE = False
    class FakeAutocompleteWidget: # Placeholder widget
        def __init__(self, url=None, **kwargs): pass
        def render(self, name, value, attrs=None, renderer=None): return f'<input type="text" name="{name}" value="{value or ""}" class="form-control" placeholder="Autocomplete not available">'
    autocomplete = type('obj', (object,), {'SelectMultiple': FakeAutocompleteWidget})()
# --- ----------------------------- ---

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        # --- [แก้ไข] ลบ image fields ออก ---
        fields = ['name', 'building', 'floor', 'location', 'capacity', 'equipment_in_room']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'equipment_in_room': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'ระบุอุปกรณ์ทีละรายการ ขึ้นบรรทัดใหม่'}),
            # --- ลบ image widgets ---
        }
        labels = {
            'name': 'ชื่อห้องประชุม', 'building': 'อาคาร', 'floor': 'ชั้น',
            'location': 'โซน/สถานที่', 'capacity': 'ความจุ (คน)', 'equipment_in_room': 'อุปกรณ์ในห้อง',
            # --- ลบ image labels ---
        }

class BookingForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        widget=autocomplete.SelectMultiple(url='user-autocomplete') if DAL_AVAILABLE else forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        required=False, label="ผู้เข้าร่วม (เลือกได้หลายคน)"
    )
    class Meta:
        model = Booking
        exclude = ['room', 'booked_by', 'status', 'created_at', 'updated_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'chairman': forms.TextInput(attrs={'class': 'form-control'}),
            'participant_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'department_meeting': forms.TextInput(attrs={'class': 'form-control'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'additional_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'additional_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'title': 'หัวข้อ/วาระการประชุม',
            'start_time': 'เวลาเริ่มต้น',
            'end_time': 'เวลาสิ้นสุด',
            'chairman': 'ประธานการประชุม (ถ้ามี)',
            'participant_count': 'จำนวนผู้เข้าร่วม',
            'participants': 'รายชื่อผู้เข้าร่วม (ค้นหาชื่อ)',
            'department_meeting': 'แผนก (สำหรับการประชุม)',
            'attachment': 'ไฟล์เอกสารนำเสนอ',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
            'additional_requests': 'คำขออุปกรณ์/บริการเพิ่มเติม',
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time"); end = cleaned_data.get("end_time")
        room = self.initial.get('room') or (self.instance.pk and self.instance.room)
        count = cleaned_data.get("participant_count")
        if room and count and count > room.capacity: raise ValidationError(f"จำนวนผู้เข้าร่วม ({count}) เกินความจุห้อง '{room.name}' ({room.capacity})")
        if start and end:
            if self.instance.pk is None and start < timezone.now(): raise ValidationError("ไม่สามารถจองเวลาย้อนหลัง")
            if end <= start: raise ValidationError("เวลาสิ้นสุดต้องหลังเวลาเริ่ม")
            if room:
                conflicts = Booking.objects.filter( room=room, start_time__lt=end, end_time__gt=start ).exclude(status__in=['REJECTED', 'CANCELLED'])
                if self.instance.pk: conflicts = conflicts.exclude(pk=self.instance.pk)
                if conflicts.exists():
                    c = conflicts.first(); c_time = f"{c.start_time:%H:%M}-{c.end_time:%H:%M}"
                    raise ValidationError(f"ห้อง '{room.name}' ไม่ว่าง มีการจอง '{c.title}' ({c_time}) อยู่แล้ว")
        return cleaned_data

# --- [ลบ] คลาส ProfileForm ทั้งหมด ---
# class ProfileForm(...):
#    ...

# --- คลาส CustomPasswordChangeForm (ยังคงอยู่) ---
class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านปัจจุบัน'})
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านใหม่'})
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ยืนยันรหัสผ่านใหม่'})