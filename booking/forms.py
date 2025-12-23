import os
import re # ใช้สำหรับตรวจสอบอักขระพิเศษ
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from dal import autocomplete

# Crispy Forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML

from .models import Booking, Room, Equipment 

# -----------------------------------------------
# 1. BookingForm (ฟอร์มจองห้อง)
# -----------------------------------------------
class BookingForm(forms.ModelForm):
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
            'end_time', 'participant_count', 'room_layout', 'room_layout_attachment',
            'equipments', 'presentation_file', 'description', 
            'additional_requests', 'additional_notes',
        ]
        
        labels = {
            'room': 'ห้องประชุม', 
            'title': 'หัวข้อการประชุม', 
            'chairman': 'ประธานในที่ประชุม (ถ้ามี)',
            'department': 'แผนกผู้จอง', 
            'start_time': 'วัน/เวลา เริ่มต้น', 
            'end_time': 'วัน/เวลา สิ้นสุด',
            'participant_count': 'จำนวนผู้เข้าร่วม (โดยประมาณ)', 
            'presentation_file': 'ไฟล์นำเสนอ (Max 100MB)', 
            'description': 'รายละเอียด/วาระการประชุม',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
            'room_layout': 'รูปแบบการจัดห้อง', 
            'room_layout_attachment': 'แนบไฟล์รูปแบบการจัดห้อง (JPEG, PNG, PDF เท่านั้น)',
            'equipments': 'อุปกรณ์ที่ต้องการเบิก (ค้นหาและเลือก)',
            'additional_requests': 'คำขออื่นๆ (กรณีไม่มีในรายการอุปกรณ์)',
        }
        help_texts = {
            'participant_count': 'ระบุจำนวนคร่าวๆ สำหรับการเตรียมห้อง',
        }
        
        widgets = {
            'room': forms.HiddenInput(),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control', 'placeholder': ''}),
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
            'room_layout': forms.RadioSelect(),
            'room_layout_attachment': forms.ClearableFileInput(attrs={'class':'form-control', 'accept': '.jpg,.jpeg,.png,.pdf'}),
            
            'equipments': autocomplete.ModelSelect2Multiple(
                url='equipment-autocomplete',
                attrs={'data-placeholder': 'พิมพ์ชื่ออุปกรณ์เพื่อค้นหา...', 'data-theme': 'bootstrap-5'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['title'].required = True
        self.fields['participant_count'].required = False
        self.fields['equipments'].required = False
        
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['start_time'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}, format='%Y-%m-%dT%H:%M')
        self.fields['end_time'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}, format='%Y-%m-%dT%H:%M')
        
        self.order_fields([
            'title', 'chairman', 'department', 'start_time', 'end_time', 
            'recurrence', 'recurrence_end_date', 'participant_count', 
            'room_layout', 'room_layout_attachment', 
            'equipments', 'additional_requests', 
            'presentation_file', 'description', 'additional_notes', 'room'
        ])

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        room = cleaned_data.get('room')
        participant_count = cleaned_data.get('participant_count')

        if start_time and end_time and start_time >= end_time:
            raise ValidationError("วัน/เวลา สิ้นสุด ต้องอยู่หลังจาก วัน/เวลา เริ่มต้น", code='invalid_time_range')
        
        if start_time:
            start_time_aware = timezone.make_aware(start_time, timezone.get_current_timezone()) if timezone.is_naive(start_time) else start_time
            if not self.instance.pk and start_time_aware < timezone.now():
                raise ValidationError("ไม่สามารถจองเวลาย้อนหลังได้ กรุณาเลือกเวลาใหม่", code='invalid_past_date')
        
        if room and participant_count and participant_count > room.capacity:
             raise ValidationError(f"จองไม่ได้: จำนวนผู้เข้าร่วม ({participant_count} คน) เกินความจุของห้อง ({room.capacity} คน)! ", code='capacity_exceeded')

        p_file = cleaned_data.get('presentation_file')
        if p_file:
            limit_mb = 100
            if p_file.size > limit_mb * 1024 * 1024:
                self.add_error('presentation_file', f"ขนาดไฟล์ใหญ่เกินกำหนด! (สูงสุด {limit_mb} MB)")

        l_file = cleaned_data.get('room_layout_attachment')
        if l_file:
            valid_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
            ext = os.path.splitext(l_file.name)[1].lower()
            if ext not in valid_extensions:
                self.add_error('room_layout_attachment', "ไฟล์ไม่ถูกต้อง: รองรับเฉพาะ JPG, PNG และ PDF เท่านั้น")

        return cleaned_data


# -----------------------------------------------
# 2. RoomForm (สำหรับ Admin จัดการห้อง)
# -----------------------------------------------
class RoomForm(forms.ModelForm):
    approver = forms.ModelChoiceField(
        queryset=User.objects.filter(Q(groups__name__in=['Approver', 'Admin']) | Q(is_superuser=True)).distinct(),
        widget=autocomplete.ModelSelect2(url='user-autocomplete', attrs={'data-placeholder': 'พิมพ์ค้นหา Admin หรือ Approver...', 'data-theme': 'bootstrap-5'}),
        required=False, 
        label="ผู้อนุมัติประจำห้อง"
    )

    class Meta:
        model = Room
        fields = '__all__'
        
        labels = {
            'name': 'ชื่อห้องประชุม',
            'building': 'อาคาร / ตึก',
            'floor': 'ชั้น',
            'location': 'สถานที่ตั้ง',
            'capacity': 'ความจุ (คน)',
            'equipment_in_room': 'อุปกรณ์ถาวรในห้อง',
            'image': 'รูปภาพห้อง',
            'is_maintenance': 'เปิดใช้งานโหมดปิดปรับปรุง',
            'maintenance_start': 'วัน/เวลา เริ่มปิดปรับปรุง',
            'maintenance_end': 'วัน/เวลา สิ้นสุดปิดปรับปรุง',
            'line_notify_token': 'Line Notify Token (สำหรับแจ้งเตือน)',
            'teams_webhook_url': 'Microsoft Teams Webhook URL',
        }
        
        widgets = {
            'maintenance_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maintenance_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}), 
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}), 
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}), 
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'line_notify_token': forms.TextInput(attrs={'class': 'form-control'}), 
            'teams_webhook_url': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['maintenance_start'].required = False
        self.fields['maintenance_end'].required = False
        self.helper = FormHelper()
        self.helper.form_tag = False 

        self.helper.layout = Layout(
            'non_field_errors', 
            Row(Column('name', css_class='col-md-6 mb-3'), Column('capacity', css_class='col-md-6 mb-3')),
            Row(Column('building', css_class='col-md-6 mb-3'), Column('floor', css_class='col-md-6 mb-3')),
            'location', 
            'equipment_in_room', 
            'image',
            HTML('<hr class="my-4">'), 
            'approver', 
            'line_notify_token', 
            'teams_webhook_url',
            HTML('<hr class="my-4">'), 
            HTML('<h5 class="text-muted mb-3"><i class="bi bi-tools"></i> ตั้งค่าการปิดปรับปรุง</h5>'),
            Row(Column('maintenance_start', css_class='col-md-6 mb-3'), Column('maintenance_end', css_class='col-md-6 mb-3')),
            Field('is_maintenance', wrapper_class="form-check form-switch fs-6 mb-3"),
        )


# -----------------------------------------------
# 3. CustomUserCreationForm (ฉบับเพิ่มกฎพิเศษ)
# -----------------------------------------------
class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(
        label="รหัสผ่าน",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'id': 'id_password',
            'placeholder': 'ตั้งรหัสผ่านของคุณ'
        }),
        help_text="", 
        required=True
    )
    
    password_confirmation = forms.CharField(
        label="ยืนยันรหัสผ่าน",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'id': 'id_password_confirmation',
            'placeholder': 'กรอกรหัสผ่านอีกครั้ง'
        }),
        required=True
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(), 
        widget=forms.CheckboxSelectMultiple, 
        required=False, 
        label="กำหนดสิทธิ์ (Groups)"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'groups']

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        
        self.fields['username'].label = "ชื่อผู้ใช้ (Username)"
        self.fields['username'].required = True
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'เช่น somchai.t'})
        
        self.fields['first_name'].label = "ชื่อจริง"
        self.fields['first_name'].required = True
        self.fields['first_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'เช่น สมชาย'})

        self.fields['last_name'].label = "นามสกุล"
        self.fields['last_name'].required = True
        self.fields['last_name'].widget.attrs.update({'class': 'form-control', 'placeholder': 'เช่น ใจดี'})

        self.fields['email'].label = "อีเมล"
        self.fields['email'].required = True
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'somchai@example.com'})

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")
        email = cleaned_data.get("email")

        # 1. เช็ครหัสผ่านตรงกัน
        if password and password_confirmation:
            if password != password_confirmation:
                raise ValidationError("รหัสผ่านทั้งสองช่องไม่ตรงกัน กรุณาตรวจสอบ")

        # 2. เช็คเงื่อนไขความปลอดภัย
        if password:
            if len(password) < 8:
                self.add_error('password', "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร")

            if not re.search(r'[a-zA-Z]', password):
                self.add_error('password', "รหัสผ่านต้องมีตัวอักษรภาษาอังกฤษ (a-z, A-Z)")

            if not re.search(r'\d', password):
                self.add_error('password', "รหัสผ่านต้องมีตัวเลข (0-9)")

            if not re.search(r'[@#$%&*()_ \[\]]', password):
                self.add_error('password', "รหัสผ่านต้องมีอักขระพิเศษอย่างน้อย 1 ตัว เช่น @#$%&*()_ []")

        # 3. เช็คอีเมลซ้ำ
        if email and User.objects.filter(email=email).exists():
            self.add_error('email', "อีเมลนี้มีผู้ใช้งานแล้ว")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            self.cleaned_data.get('groups', []) 
            self.save_m2m()
            
            if user.groups.filter(name='Admin').exists():
                user.is_staff = True
                user.is_superuser = True
                user.save()
                
        return user


# -----------------------------------------------
# 4. EquipmentForm
# -----------------------------------------------
class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ['name', 'description']
        labels = {'name': 'ชื่ออุปกรณ์', 'description': 'รายละเอียด / หมายเหตุ'}
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }