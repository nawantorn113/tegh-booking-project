# booking/forms.py (ฉบับเต็ม)

from django import forms
from django.contrib.auth.models import User
from .models import Room, Booking, Profile
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
    # Placeholder widget
    class FakeAutocompleteWidget:
        def __init__(self, url=None, **kwargs): pass
        def render(self, name, value, attrs=None, renderer=None): return f'<input type="text" name="{name}" value="{value or ""}" class="form-control" placeholder="Autocomplete not available">'
    autocomplete = type('obj', (object,), {'SelectMultiple': FakeAutocompleteWidget})()
# --- ----------------------------- ---

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        # Fields ต้องตรงกับ Model
        fields = ['name', 'building', 'floor', 'location', 'capacity', 'equipment_in_room', 'image1', 'image2', 'image3']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'equipment_in_room': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'ระบุอุปกรณ์ทีละรายการ ขึ้นบรรทัดใหม่'}),
            'image1': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'image2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'image3': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'ชื่อห้องประชุม', 'building': 'อาคาร', 'floor': 'ชั้น',
            'location': 'โซน/สถานที่', 'capacity': 'ความจุ (คน)', 'equipment_in_room': 'อุปกรณ์ในห้อง',
            'image1': 'รูปภาพ 1', 'image2': 'รูปภาพ 2', 'image3': 'รูปภาพ 3',
        }

class BookingForm(forms.ModelForm):
    # ⬇️ [Fields ที่เพิ่มเข้ามาสำหรับ Recurrence] ⬇️
    recurrence_type = forms.ChoiceField(
        choices=Booking.RECURRENCE_CHOICES, 
        initial='NONE', 
        required=True,
        label="การจองซ้ำ",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    repeat_until = forms.DateField(
        required=False,
        label="ซ้ำจนถึงวันที่",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # นิยาม Field 'participants' แยกต่างหาก
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        widget=autocomplete.SelectMultiple(url='user-autocomplete') if DAL_AVAILABLE else forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        required=False, label="ผู้เข้าร่วม (เลือกได้หลายคน)"
    )

    class Meta:
        model = Booking
        # ⬇️ [แก้ไข] fields ต้องรวม Field ที่เพิ่มใหม่ (recurrence_type, repeat_until) ⬇️
        fields = [
            'title', 'start_time', 'end_time', 
            'recurrence_type', 'repeat_until', 
            'chairman', 'participant_count', 'participants', 
            'department_meeting', 'additional_requests', 
            'additional_notes', 'attachment',
        ]
        
        # --- กำหนด Widgets ให้ตรงกับ Field ที่มีใน Model ---
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
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        room = self.initial.get('room') or (self.instance.pk and self.instance.room)
        count = cleaned_data.get("participant_count")
        
        # ⬇️ [Logic สำหรับ Recurring] ตรวจสอบเงื่อนไขการจองซ้ำ
        recurrence = cleaned_data.get("recurrence_type")
        repeat_until = cleaned_data.get("repeat_until")
        
        if recurrence != 'NONE' and not repeat_until:
            raise ValidationError("หากเลือกการจองซ้ำ ต้องระบุ 'ซ้ำจนถึงวันที่'")
        
        if repeat_until and start and repeat_until < start.date():
            raise ValidationError("วันที่สิ้นสุดการซ้ำต้องไม่ย้อนหลังกว่าวันที่เริ่มต้นการจอง")
        # ⬆️ [Logic สำหรับ Recurring] ⬆️

        if room and count and count > room.capacity:
             raise ValidationError(f"จำนวนผู้เข้าร่วม ({count}) เกินความจุห้อง '{room.name}' ({room.capacity})")

        if start and end:
             if self.instance.pk is None and start < timezone.now(): raise ValidationError("ไม่สามารถจองเวลาย้อนหลัง")
             if end <= start: raise ValidationError("เวลาสิ้นสุดต้องหลังเวลาเริ่ม")
             if room:
                 # Check current conflicts (ไม่ซ้ำซ้อน)
                 conflicts = Booking.objects.filter( room=room, start_time__lt=end, end_time__gt=start ).exclude(status__in=['REJECTED', 'CANCELLED'])
                 if self.instance.pk: conflicts = conflicts.exclude(pk=self.instance.pk)
                 if conflicts.exists():
                     c = conflicts.first(); c_time = f"{c.start_time:%H:%M}-{c.end_time:%H:%M}"
                     raise ValidationError(f"ห้อง '{room.name}' ไม่ว่าง มีการจอง '{c.title}' ({c_time}) อยู่แล้ว")
        return cleaned_data

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านปัจจุบัน'})
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'รหัสผ่านใหม่'})
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ยืนยันรหัสผ่านใหม่'})