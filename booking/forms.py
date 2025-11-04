# booking/forms.py
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Booking, Room 
from django.contrib.auth.models import User
from django.urls import reverse_lazy 

from dal import autocomplete
from django.utils import timezone
from django.core.exceptions import ValidationError


class BookingForm(forms.ModelForm):
    
    # (ฟิลด์สำหรับ "จองซ้ำ")
    RECURRENCE_CHOICES = [
        ('NONE', 'ไม่จองซ้ำ'),
        ('WEEKLY', 'จองซ้ำทุกสัปดาห์ (ในวันเดียวกัน)'),
        ('MONTHLY', 'จองซ้ำทุกเดือน (ในวันที่เดียวกัน)'),
    ]
    recurrence = forms.ChoiceField(
        choices=RECURRENCE_CHOICES, 
        required=False, 
        label="การจองซ้ำ",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    recurrence_end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), 
        required=False, 
        label="สิ้นสุดการจองซ้ำ"
    )

    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'chairman', 'department', 'start_time',
            'end_time', 'participant_count', 
            'participants', 
            'presentation_file', 
            'description', 'additional_requests', 'additional_notes',
        ]
        
        labels = {
            'room': 'ห้องประชุม',
            'title': 'หัวข้อการประชุม',
            'chairman': 'ประธานในที่ประชุม (ถ้ามี)',
            'department': 'แผนกผู้จอง',
            'start_time': 'วัน/เวลา เริ่มต้น',
            'end_time': 'วัน/เวลา สิ้นสุด',
            'participant_count': 'จำนวนผู้เข้าร่วม',
            'participants': 'รายชื่อผู้เข้าร่วม',
            'presentation_file': 'ไฟล์นำเสนอ (ถ้ามี)',
            'description': 'รายละเอียด/วาระการประชุม',
            'additional_requests': 'คำขอเพิ่มเติม (เช่น อุปกรณ์พิเศษ)',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
        }
        
        # --- 💡 [แก้ไขจุดที่ 1] 💡 ---
        # (ลบ 'participants' ออกจาก help_texts เพื่อไม่ให้มันแสดงข้างนอก)
        help_texts = {
            'participant_count': '',
            'presentation_file': 'ไฟล์ที่ต้องการนำเสนอ',
        }
        
        widgets = {
            'room': forms.HiddenInput(),
            
            # --- 💡 [แก้ไขจุดที่ 2] 💡 ---
            # (ย้ายข้อความจาก help_texts มาใส่ใน 'data-placeholder' แทน)
            'participants': autocomplete.ModelSelect2Multiple(
                url='user-autocomplete',
                attrs={'data-placeholder': 'พิมพ์ชื่อ, นามสกุล, หรือ username เพื่อค้นหา...', 'data-theme': 'bootstrap-5'}
            ),

            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control', 'placeholder': ''}),
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
        }

    # (โค้ด __init__ นี้ถูกต้องแล้ว ทำให้ช่องเวลาแสดงผล)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']
        
        self.fields['start_time'].widget = forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M'
        )
        self.fields['end_time'].widget = forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M'
        )
        
        field_order = [
            'title', 'chairman', 'department',
            'start_time', 'end_time',
            'recurrence', 'recurrence_end_date',
            'participant_count', 'participants',
            'presentation_file', 'description', 
            'additional_requests', 'additional_notes',
            'room'
        ]
        self.order_fields(field_order)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        recurrence = cleaned_data.get('recurrence')
        recurrence_end_date = cleaned_data.get('recurrence_end_date')

        if start_time:
            if timezone.is_naive(start_time):
                start_time_aware = timezone.make_aware(start_time, timezone.get_current_timezone())
            else:
                start_time_aware = start_time
                
            if start_time_aware < timezone.now():
                raise ValidationError(
                    "ไม่สามารถจองเวลาย้อนหลังได้ กรุณาเลือกเวลาใหม่",
                    code='invalid_past_date'
                )
        
        if recurrence and recurrence != 'NONE':
            if not recurrence_end_date:
                self.add_error('recurrence_end_date', 'กรุณาระบุวันที่สิ้นสุดการจองซ้ำ')
            elif recurrence_end_date <= start_time.date():
                self.add_error('recurrence_end_date', 'วันที่สิ้นสุด ต้องอยู่หลังจาก วันที่เริ่มต้น')

        return cleaned_data


class CustomPasswordChangeForm(PasswordChangeForm):
     old_password = forms.CharField( label="รหัสผ่านเก่า", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'autofocus': True, 'class':'form-control'}), )
     new_password1 = forms.CharField( label="รหัสผ่านใหม่", widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), strip=False, )
     new_password2 = forms.CharField( label="ยืนยันรหัสผ่านใหม่", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), )

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'building', 'floor', 'capacity', 'equipment_in_room', 'location', 'image'] 
        labels = {
            'name': 'ชื่อห้องประชุม', 'building': 'อาคาร', 'floor': 'ชั้น',
            'capacity': 'ความจุ (คน)', 'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'location': 'ตำแหน่ง (เช่น ใกล้ฝ่ายบุคคล)',
            'image': 'รูปภาพ (รูปหลัก)',
        }
        help_texts = {
            'equipment_in_room': 'ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่ เช่น โปรเจคเตอร์, ไวท์บอร์ด',
            'image': 'เลือกไฟล์รูปภาพ .jpg, .png',
            'capacity': 'ระบุเป็นตัวเลขเท่านั้น',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'เช่น ห้องประชุม O1-1', 'class':'form-control'}),
            'building': forms.TextInput(attrs={'placeholder': 'เช่น สำนักงาน 1, อาคาร R&D', 'class':'form-control'}),
            'floor': forms.TextInput(attrs={'placeholder': 'เช่น ชั้น 1, ชั้น 5', 'class':'form-control'}),
            'capacity': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'placeholder': 'โปรเจคเตอร์\nไวท์บอร์ด\nชุดเครื่องเสียง\nปลั๊กไฟ', 'class':'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': 'เช่น ใกล้ฝ่ายบุคคล, โซน R&D', 'class':'form-control'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class':'form-control'}),
        }