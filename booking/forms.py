import os
import re
from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.safestring import mark_safe 
from dal import autocomplete 

from .models import Booking, Room, Equipment, UserProfile 

# --- 1. Custom Widget ---
class CustomImageWidget(forms.ClearableFileInput):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        if value and hasattr(value, "url"):
            image_html = f"""
                <div class="mb-3 p-3 border rounded bg-light text-center position-relative">
                    <img src="{value.url}" alt="Room Preview" 
                         class="img-fluid rounded shadow-sm" 
                         style="max-height: 250px; max-width: 100%; object-fit: contain;">
                    <div class="mt-2 text-primary small fw-bold">
                        <i class="bi bi-check-circle-fill"></i> รูปภาพปัจจุบัน
                    </div>
                </div>
            """
            output.append(image_html)
        output.append(super().render(name, value, attrs, renderer))
        return mark_safe(''.join(output))

# --- 2. Booking Form ---
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
            'room', 'title', 'booking_type', 'chairman', 'department', 'start_time', 
            'end_time', 'participant_count', 'room_layout', 
            'room_layout_attachment', 'equipments', 
            'presentation_file', 'presentation_link', 
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
            'presentation_link': forms.URLInput(attrs={
                'class': 'form-control', 
                'placeholder': 'เช่น https://www.canva.com/...'
            }),

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
            
            'booking_type': forms.Select(attrs={'class': 'form-select bg-light border-primary fw-bold'}),
        }
        
        labels = {
            'title': 'หัวข้อการประชุม',
            'booking_type': 'ประเภทกิจกรรม',
            'chairman': 'ประธานในที่ประชุม',
            'department': 'แผนก/หน่วยงาน',
            'participant_count': 'จำนวนผู้เข้าประชุม',
            'description': 'รายละเอียดเพิ่มเติม',
            'additional_requests': 'ความต้องการเพิ่มเติม',
            'additional_notes': 'หมายเหตุ',
            'room_layout': 'รูปแบบการจัดห้อง',
            'room_layout_attachment': 'ไฟล์แนบผังห้อง (ถ้ามี)',
            'presentation_file': 'ไฟล์นำเสนอ (Upload)',
            'presentation_link': 'ลิงก์เอกสารออนไลน์ (URL)',
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

        # ==========================================================
        # [แก้ไขแล้ว] เปลี่ยนจาก 'internal' เป็น 'general' ให้ตรงกับ Database
        # ==========================================================
        self.fields['booking_type'].required = False  
        self.fields['booking_type'].initial = 'general'  
        self.fields['booking_type'].widget = forms.HiddenInput() 

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        
        # [แก้ไขแล้ว] เปลี่ยนจาก 'internal' เป็น 'general'
        if not cleaned_data.get('booking_type'):
            cleaned_data['booking_type'] = 'general'

        if start and end and start >= end:
            self.add_error('end_time', "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")
            
        if start:
            if timezone.is_naive(start):
                start = timezone.make_aware(start, timezone.get_current_timezone())
            if not self.instance.pk and start < timezone.now():
                self.add_error('start_time', "ไม่สามารถจองเวลาย้อนหลังได้")
                
        return cleaned_data

# --- 3. Room Form (แก้ไขห้อง + แจ้งทำความสะอาด) ---
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

    is_cleaning = forms.BooleanField(
        required=False, 
        label="แจ้งแม่บ้านทำความสะอาด (สร้าง Booking อัตโนมัติ)",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input', 
            'id': 'cleaningCheck',
            'onchange': 'toggleCleaningInputs()' 
        })
    )
    cleaning_start = forms.DateTimeField(
        required=False, 
        label="เริ่มเวลา",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'id': 'cleanStart'})
    )
    cleaning_end = forms.DateTimeField(
        required=False, 
        label="สิ้นสุดเวลา",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'id': 'cleanEnd'})
    )

    class Meta:
        model = Room
        fields = [
            'name', 'capacity', 'equipment_in_room', 'image', 'location', 
            'floor', 'building', 'is_maintenance', 'maintenance_start', 
            'maintenance_end', 'description', 'is_active', 'status_note', 'approver'
        ]
        
        labels = {
            'name': 'ชื่อห้องประชุม',
            'capacity': 'ความจุ (คน)',
            'location': 'สถานที่ตั้ง',
            'floor': 'ชั้น',
            'building': 'อาคาร',
            'description': 'รายละเอียดห้อง',
            'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'image': 'รูปภาพห้อง',
            'approver': 'ผู้อนุมัติประจำห้อง',
            'is_maintenance': 'เปิดใช้งานโหมดปิดปรับปรุง',
            'maintenance_start': 'เริ่มปิดปรับปรุง',
            'maintenance_end': 'สิ้นสุดปิดปรับปรุง',
            'status_note': 'หมายเหตุแจ้งเตือน (แสดงหน้า Dashboard)',
        }

        widgets = {
            'image': CustomImageWidget(),
            'maintenance_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maintenance_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch', 'id': 'maintenanceCheck'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status_note': forms.TextInput(attrs={
                'class': 'form-control border-warning text-warning-emphasis', 
                'placeholder': 'ระบุข้อความแจ้งเตือน (ถ้ามี) เช่น ทีวีใช้งานไม่ได้'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['maintenance_start'].required = False
        self.fields['maintenance_end'].required = False

    def clean(self):
        cleaned_data = super().clean()
        
        is_maintenance = cleaned_data.get('is_maintenance')
        if not is_maintenance:
            cleaned_data['maintenance_start'] = None
            cleaned_data['maintenance_end'] = None
            
        is_cl = cleaned_data.get('is_cleaning')
        cl_start = cleaned_data.get('cleaning_start')
        cl_end = cleaned_data.get('cleaning_end')
        
        if is_cl:
            if not cl_start or not cl_end:
                raise ValidationError("กรุณาระบุเวลาเริ่มและสิ้นสุดการทำความสะอาด")
            if cl_start >= cl_end:
                self.add_error('cleaning_end', "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.is_maintenance:
            instance.maintenance_start = None
            instance.maintenance_end = None
        
        if commit:
            instance.save()
        return instance

# --- 4. Equipment Form ---
class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = '__all__'
        labels = {
            'name': 'ชื่ออุปกรณ์',
            'description': 'รายละเอียด',
            'status_note': 'หมายเหตุสถานะ',
            'is_active': 'เปิดใช้งาน (Active)' 
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status_note': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

# --- 5. Custom User Forms ---
class CustomUserCreationForm(forms.ModelForm):
    first_name = forms.CharField(label="ชื่อจริง", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="นามสกุล", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.CharField(label="แผนก / หน่วยงาน", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="อีเมล", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="รหัสผ่าน", widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)
    password_confirmation = forms.CharField(label="ยืนยันรหัสผ่าน", widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)
    groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), widget=forms.CheckboxSelectMultiple, required=False, label="กำหนดสิทธิ์")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'groups']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("password_confirmation"):
            self.add_error('password_confirmation', "รหัสผ่านไม่ตรงกัน")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
            if self.cleaned_data.get('department'):
                UserProfile.objects.update_or_create(user=user, defaults={'department': self.cleaned_data['department']})
        return user

class CustomUserEditForm(forms.ModelForm):
    first_name = forms.CharField(label="ชื่อจริง", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="นามสกุล", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.CharField(label="แผนก / หน่วยงาน", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="อีเมล", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'readonly': 'readonly'})
        if self.instance.pk and hasattr(self.instance, 'profile'):
            self.fields['department'].initial = self.instance.profile.department

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if self.cleaned_data.get('department'):
                UserProfile.objects.update_or_create(user=user, defaults={'department': self.cleaned_data['department']})
        return user