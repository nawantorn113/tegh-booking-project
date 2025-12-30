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

# =========================================================
# 1. Custom Widget (ตัวช่วยแสดงรูปภาพ)
# =========================================================
class CustomImageWidget(forms.ClearableFileInput):
    def render(self, name, value, attrs=None, renderer=None):
        output = []
        # ถ้ามีรูปภาพอยู่แล้ว ให้แสดงรูป
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
        
        # แสดงปุ่ม Upload ปกติ
        output.append(super().render(name, value, attrs, renderer))
        return mark_safe(''.join(output))


# =========================================================
# 2. Booking Form (ฟอร์มจองห้อง)
# =========================================================
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


# =========================================================
# 3. Room Form (ฟอร์มจัดการห้อง) **จุดที่แก้ไข**
# =========================================================
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
        
        # --- WIDGETS CONFIGURATION ---
        widgets = {
            # [!] สำคัญ: เช็คชื่อ Field ใน models.py ของคุณ
            # ถ้าชื่อ 'image' ให้ใช้บรรทัดนี้:
            'image': CustomImageWidget(),
            
            # ถ้าใน models.py ชื่อ 'room_image' ให้เปิดบรรทัดล่างนี้แทน:
            # 'room_image': CustomImageWidget(),

            'maintenance_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maintenance_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'floor': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['maintenance_start'].required = False
        self.fields['maintenance_end'].required = False


# =========================================================
# 4. Custom User Form (เพิ่มผู้ใช้ใหม่)
# =========================================================
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
        labels = {'username': 'ชื่อผู้ใช้ (Username)'}
        help_texts = {'username': 'ใช้สำหรับเข้าสู่ระบบ (ภาษาอังกฤษ ตัวเลข หรือ @/./+/-/_ เท่านั้น)'}

    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'เช่น somchai.j'})
        
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
            qs = User.objects.filter(email=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('email', "อีเมลนี้มีผู้ใช้งานในระบบแล้ว")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            self.cleaned_data.get('groups', []) 
            self.save_m2m()
            
            if user.groups.filter(name='Admin').exists():
                user.is_staff = True
                user.is_superuser = True
                user.save()
            else:
                if user.is_staff and not user.is_superuser:
                      user.is_staff = False
                      user.save()

            dept = self.cleaned_data.get('department')
            if dept:
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile.department = dept
                profile.save()
        return user


# =========================================================
# 5. Custom User Edit Form (แก้ไขข้อมูลผู้ใช้ - ไม่มีรหัสผ่าน)
# =========================================================
class CustomUserEditForm(forms.ModelForm):
    first_name = forms.CharField(
        label="ชื่อจริง", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="นามสกุล", 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        label="แผนก / หน่วยงาน",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="อีเมล", 
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {'username': 'ชื่อผู้ใช้ (Username)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'readonly': 'readonly'})
        
        if self.instance.pk and hasattr(self.instance, 'profile'):
            self.fields['department'].initial = self.instance.profile.department

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("อีเมลนี้มีผู้ใช้งานแล้ว")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            dept = self.cleaned_data.get('department')
            if dept:
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.department = dept
                profile.save()
        return user


# =========================================================
# 6. Equipment Form (ฟอร์มจัดการอุปกรณ์)
# =========================================================
class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ['name', 'description', 'is_active', 'status_note']
        labels = {
            'name': 'ชื่ออุปกรณ์', 
            'description': 'รายละเอียด',
            'is_active': 'สถานะพร้อมใช้งาน',
            'status_note': 'หมายเหตุ (กรณีชำรุด/ส่งซ่อม)'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'status_note': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ระบุสาเหตุการเสีย (ถ้ามี)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }