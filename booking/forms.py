from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User, Group
from .models import Booking, Room 
from dal import autocomplete
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q 

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML

# -----------------------------------------------
# 1. BookingForm
# -----------------------------------------------
class BookingForm(forms.ModelForm):
    # ... (โค้ด BookingForm เดิมของคุณ ถูกต้องแล้ว) ...
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
        # ... (Labels, Help texts, Widgets เดิมของคุณ) ...
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
        
        widgets = {
            'room': forms.HiddenInput(),
            'participants': autocomplete.ModelSelect2Multiple(
                url='user-autocomplete',
                attrs={'data-placeholder': 'พิมพ์ชื่อ, นามสกุล, หรือ username เพื่อค้นหา...', 'data-theme': 'bootstrap-5'}
            ),
            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control', 'placeholder': ''}),
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['participants'].required = False 
        self.fields['title'].required = True
        self.fields['participant_count'].required = False
        
        self.fields['start_time'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_time'].input_formats = ['%Y-%m-%dT%H:%M']
        
        self.fields['start_time'].widget = forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}, 
            format='%Y-%m-%dT%H:%M'
        )
        self.fields['end_time'].widget = forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control', 'required': 'required'}, 
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
        end_time = cleaned_data.get('end_time') 
        recurrence = cleaned_data.get('recurrence')
        recurrence_end_date = cleaned_data.get('recurrence_end_date')
        
        room = cleaned_data.get('room')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError("วัน/เวลา สิ้นสุด ต้องอยู่หลังจาก วัน/เวลา เริ่มต้น", code='invalid_time_range')

        if start_time:
            if timezone.is_naive(start_time):
                start_time_aware = timezone.make_aware(start_time, timezone.get_current_timezone())
            else:
                start_time_aware = start_time
                
            if not self.instance.pk and start_time_aware < timezone.now():
                raise ValidationError(
                    "ไม่สามารถจองเวลาย้อนหลังได้ กรุณาเลือกเวลาใหม่",
                    code='invalid_past_date'
                )
        
        if recurrence and recurrence != 'NONE':
            if not recurrence_end_date:
                self.add_error('recurrence_end_date', 'กรุณาระบุวันที่สิ้นสุดการจองซ้ำ')
            elif recurrence_end_date and start_time and recurrence_end_date <= start_time.date():
                self.add_error('recurrence_end_date', 'วันที่สิ้นสุด ต้องอยู่หลังจาก วันที่เริ่มต้น')
        
        if 'participant_count' not in cleaned_data or cleaned_data.get('participant_count') is None:
            cleaned_data['participant_count'] = 1 
        
        participant_count = cleaned_data.get('participant_count')

        if room and participant_count:
            if participant_count > room.capacity:
                raise ValidationError(
                    f"จองไม่ได้: จำนวนผู้เข้าร่วม ({participant_count} คน) เกินความจุของห้อง ({room.capacity} คน)! "
                    "กรุณาลดจำนวนคน หรือติดต่อผู้ดูแล",
                    code='capacity_exceeded'
                )

        return cleaned_data


# -----------------------------------------------
# 2. CustomPasswordChangeForm
# -----------------------------------------------
class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField( 
        label="รหัสผ่านเก่า", 
        strip=False, 
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'autofocus': True, 'class':'form-control'}), 
    )
    new_password1 = forms.CharField( 
        label="รหัสผ่านใหม่", 
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), 
        strip=False, 
    )
    new_password2 = forms.CharField( 
        label="ยืนยันรหัสผ่านใหม่", 
        strip=False, 
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), 
    )


# -----------------------------------------------
# 3. RoomForm
# -----------------------------------------------
class RoomForm(forms.ModelForm):
    
    approver = forms.ModelChoiceField(
        queryset=User.objects.filter(Q(groups__name__in=['Approver', 'Admin']) | Q(is_superuser=True)).distinct(),
        widget=autocomplete.ModelSelect2(
            url='user-autocomplete', 
            attrs={'data-placeholder': 'พิมพ์ค้นหา Admin หรือ Approver...', 'data-theme': 'bootstrap-5'}
        ),
        required=False,
        label="ผู้อนุมัติประจำห้อง"
    )

    class Meta:
        model = Room
        
        fields = [
            'name', 'building', 'floor', 'capacity', 'equipment_in_room', 
            'location', 'image', 'approver', 
            'maintenance_start', 'maintenance_end',
            'is_maintenance',
            'line_notify_token',
            'teams_webhook_url'
        ] 
        
        labels = {
            'name': 'ชื่อห้องประชุม', 'building': 'อาคาร', 'floor': 'ชั้น',
            'capacity': 'ความจุ (คน)', 'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'location': 'ตำแหน่ง ',
            'image': 'รูปภาพ (รูปหลัก)',
            'approver': 'ผู้อนุมัติประจำห้อง',
            'is_maintenance': 'ปิดปรับปรุง (Maintenance)', 
            'line_notify_token': 'LINE Notify Token', 
            'teams_webhook_url': 'Teams Webhook URL',
        }
        help_texts = {
            'equipment_in_room': 'ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่ เช่น โปรเจคเตอร์, ไวท์บอร์ด',
            'image': 'เลือกไฟล์รูปภาพ .jpg, .png',
            'capacity': 'ระบุเป็นตัวเลขเท่านั้น',
            'approver': 'หากเว้นว่าง ระบบจะใช้ Admin กลางในการอนุมัติ',
            'is_maintenance': 'ติ๊ก [✓] เพื่อปิดการจองห้องนี้ชั่วคราว (โหมด Manual)', 
            'line_notify_token': 'วาง Token 43 ตัวอักษร จาก LINE Notify', 
            'teams_webhook_url': 'วาง URL ที่คัดลอกจาก Teams Incoming Webhook',
        }
        
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'เช่น ห้องประชุม O1-1', 'class':'form-control'}),
            'building': forms.TextInput(attrs={'placeholder': 'เช่น สำนักงาน 1, อาคาร R&D', 'class':'form-control'}),
            'floor': forms.TextInput(attrs={'placeholder': 'เช่น ชั้น 1, ชั้น 5', 'class':'form-control'}),
            'capacity': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'placeholder': 'โปรเจคเตอร์\nไวท์บอร์ด\nชุดเครื่องเสียง\nปลั๊กไฟ', 'class':'form-control'}),
            'location': forms.TextInput(attrs={'placeholder': ' ', 'class':'form-control'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class':'form-control'}),
            
            'maintenance_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'maintenance_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'is_maintenance': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            
            'line_notify_token': forms.TextInput(attrs={'class':'form-control', 'placeholder': 'วาง Token ที่คัดลอกมาที่นี่...'}),
            'teams_webhook_url': forms.Textarea(attrs={'class':'form-control', 'rows': 3, 'placeholder': 'วาง URL ที่คัดลอกมาที่นี่...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['maintenance_start'].required = False
        self.fields['maintenance_end'].required = False
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False 

        self.helper.layout = Layout(
            'non_field_errors', 
            
            Row(
                Column('name', css_class='col-md-6 mb-3'),
                Column('capacity', css_class='col-md-6 mb-3')
            ),
            Row(
                Column('building', css_class='col-md-6 mb-3'),
                Column('floor', css_class='col-md-6 mb-3')
            ),
            'location',
            'equipment_in_room',
            'image',
            
            HTML('<hr class="my-4">'),
            'approver',
            'line_notify_token',
            'teams_webhook_url',
            
            HTML('<hr class="my-4">'),
            HTML('<p class="text-muted">ตั้งค่าการปิดปรับปรุง (Maintenance)</p>'),
            
            Row(
                Column('maintenance_start', css_class='col-md-6 mb-3'),
                Column('maintenance_end', css_class='col-md-6 mb-3')
            ),
            
            Field('is_maintenance', css_class="form-check form-switch fs-6 mb-3"),
        )

# -----------------------------------------------
# 4. CustomUserCreationForm (แยกออกมาข้างนอกแล้ว ✅)
# -----------------------------------------------
class CustomUserCreationForm(UserCreationForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="กำหนดสิทธิ์ (Groups)"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'groups']

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self.save_m2m()
            if user.groups.filter(name='Admin').exists():
                user.is_staff = True
                user.is_superuser = True
                user.save()
        return user