import os
import re
from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

# ต้องติดตั้ง: pip install django-autocomplete-light
from dal import autocomplete 

from .models import Booking, Room, Equipment, UserProfile 

# -----------------------------------------------
# 1. Booking Form (ฟอร์มจองห้อง)
# -----------------------------------------------
class BookingForm(forms.ModelForm):
    RECURRENCE_CHOICES = [
        ('NONE', 'ไม่จองซ้ำ'),
        ('WEEKLY', 'ทุกสัปดาห์ (วันเดียวกัน)'),
        ('MONTHLY', 'ทุกเดือน (วันที่เดียวกัน)')
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
        label="สิ้นสุดวันที่"
    )

    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'chairman', 'department', 'start_time', 
            'end_time', 'participant_count', 'room_layout', 
            'room_layout_attachment', 'equipments', 'presentation_file', 
            'description', 'additional_requests', 'additional_notes'
        ]
        
        widgets = {
            'room': forms.HiddenInput(),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control'}),
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'room_layout_attachment': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'room_layout': forms.RadioSelect(attrs={'class': 'layout-option-input'}),
            'equipments': autocomplete.ModelSelect2Multiple(
                url='equipment-autocomplete',
                attrs={
                    'data-placeholder': 'พิมพ์ชื่ออุปกรณ์เพื่อค้นหา...', 
                    'data-theme': 'bootstrap-5', 
                    'class': 'form-control'
                }
            ),
        }
        
        labels = {
            'title': 'หัวข้อการประชุม',
            'chairman': 'ประธานในที่ประชุม',
            'department': 'แผนก/หน่วยงาน',
            'participant_count': 'จำนวนผู้เข้าประชุม',
            'description': 'รายละเอียดเพิ่มเติม',
            'additional_requests': 'ความต้องการเพิ่มเติม',
            'additional_notes': 'หมายเหตุ',
            'room_layout': 'รูปแบบการจัดห้อง',
            'room_layout_attachment': 'ไฟล์แนบผังห้อง (ถ้ามี)',
            'presentation_file': 'ไฟล์นำเสนอ (Presentation)',
            'equipments': 'อุปกรณ์ที่ต้องการ',
            'start_time': 'เวลาเริ่ม',
            'end_time': 'เวลาสิ้นสุด',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['room_layout'].required = False 
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']

        self.order_fields([
            'title', 'chairman', 'department', 'start_time', 'end_time', 
            'recurrence', 'recurrence_end_date',
            'participant_count', 
            'room_layout', 'room_layout_attachment', 
            'equipments', 'presentation_file', 
            'description', 'additional_requests', 'additional_notes', 'room'
        ])

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        
        if start and end and start >= end:
            self.add_error('end_time', "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")
            
        if start:
            if timezone.is_naive(start):
                start = timezone.make_aware(start, timezone.get_current_timezone())
            if not self.instance.pk and start < timezone.now():
                self.add_error('start_time', "ไม่สามารถจองเวลาย้อนหลังได้")
                
        return cleaned_data


# -----------------------------------------------
# 2. Room Form (ฟอร์มจัดการห้อง)
# -----------------------------------------------
class RoomForm(forms.ModelForm):
    approver = forms.ModelChoiceField(
        queryset=User.objects.filter(Q(groups__name__in=['Approver', 'Admin']) | Q(is_superuser=True)).distinct(),
        widget=autocomplete.ModelSelect2(
            url='user-autocomplete', 
            attrs={'data-placeholder': 'ค้นหา Admin หรือ Approver...', 'data-theme': 'bootstrap-5'}
        ),
        required=False, 
        label="ผู้อนุมัติประจำห้อง"
    )

    class Meta:
        model = Room
        fields = '__all__'
        
        labels = {
            'name': 'ชื่อห้องประชุม',
            'capacity': 'ความจุ (คน)',
            'equipment_in_room': 'อุปกรณ์ถาวรในห้อง',
            'image': 'รูปภาพห้อง',
            'is_maintenance': 'เปิดใช้งานโหมดปิดปรับปรุง',
            'maintenance_start': 'วัน/เวลา เริ่มปิดปรับปรุง',
            'maintenance_end': 'วัน/เวลา สิ้นสุดปิดปรับปรุง',
            'location': 'สถานที่',
            'floor': 'ชั้น',
            'building': 'อาคาร',
            'description': 'รายละเอียดเพิ่มเติม',
            'is_active': 'สถานะใช้งาน',
        }
        
        widgets = {
            'maintenance_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maintenance_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['maintenance_start'].required = False
        self.fields['maintenance_end'].required = False


# -----------------------------------------------
# 3. Custom User Form (แก้ไขภาษาไทย + เพิ่มแผนก)
# -----------------------------------------------
class CustomUserCreationForm(forms.ModelForm):
    first_name = forms.CharField(
        label="ชื่อจริง", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น สมชาย'})
    )
    last_name = forms.CharField(
        label="นามสกุล", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น ใจดี'})
    )
    # [เพิ่ม] ช่องกรอกแผนก
    department = forms.CharField(
        label="แผนก / หน่วยงาน",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'เช่น ฝ่ายไอที, ฝ่ายบัญชี'})
    )
    email = forms.EmailField(
        label="อีเมล", 
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@tegh.com'})
    )
    
    password = forms.CharField(
        label="รหัสผ่าน",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'ตั้งรหัสผ่านอย่างน้อย 8 ตัวอักษร'}),
        required=True,
        help_text="รหัสผ่านควรมีความยาวอย่างน้อย 8 ตัวอักษร"
    )
    password_confirmation = forms.CharField(
        label="ยืนยันรหัสผ่าน",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'กรอกรหัสผ่านอีกครั้งเพื่อยืนยัน'}),
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
        
        labels = {
            'username': 'ชื่อผู้ใช้ (Username)',
        }
        help_texts = {
            'username': 'ใช้สำหรับเข้าสู่ระบบ (ภาษาอังกฤษ ตัวเลข หรือ @/./+/-/_ เท่านั้น)',
        }

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'เช่น somchai.j'})
        
        # ถ้าเป็นการแก้ไขข้อมูลเก่า ให้ดึงแผนกเดิมมาแสดง
        if self.instance.pk and hasattr(self.instance, 'profile'):
            self.fields['department'].initial = self.instance.profile.department

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")
        email = cleaned_data.get("email")

        if password and password_confirmation and password != password_confirmation:
            self.add_error('password_confirmation', "รหัสผ่านทั้งสองช่องไม่ตรงกัน")

        if email:
            # เช็คอีเมลซ้ำ (ยกเว้นตัวเองกรณีแก้ไข)
            qs = User.objects.filter(email=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('email', "อีเมลนี้มีผู้ใช้งานในระบบแล้ว")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # ถ้ามีการกรอกรหัสผ่านใหม่ (หรือสร้าง user ใหม่) ให้ตั้งรหัสผ่าน
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            self.cleaned_data.get('groups', []) 
            self.save_m2m()
            
            # บันทึกสิทธิ์ Admin อัตโนมัติถ้าเลือกกลุ่ม Admin
            if user.groups.filter(name='Admin').exists():
                user.is_staff = True
                user.is_superuser = True
                user.save()
            else:
                # ถ้าเอา Admin ออก ก็ต้องถอนสิทธิ์ด้วย
                if user.is_staff and not user.is_superuser: # ป้องกันแก้ superuser หลัก
                     user.is_staff = False
                     user.save()

            # [ส่วนสำคัญ] บันทึกแผนกลงใน UserProfile
            dept = self.cleaned_data.get('department')
            if dept:
                # ใช้ get_or_create เพื่อป้องกัน error ถ้า profile ไม่มีอยู่จริง
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.department = dept
                profile.save()
                
        return user


# -----------------------------------------------
# 4. Equipment Form (ฟอร์มจัดการอุปกรณ์)
# -----------------------------------------------
class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ['name', 'description']
        labels = {
            'name': 'ชื่ออุปกรณ์', 
            'description': 'รายละเอียด / หมายเหตุ'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }