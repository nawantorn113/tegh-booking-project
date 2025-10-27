# booking/forms.py
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Booking, Profile, Room
from django.contrib.auth.models import User
from django.urls import reverse_lazy # 1. 🟢 เพิ่ม Import นี้ 🟢

# --- ❌ ลบ Import ของ dal ทั้งหมด ❌ ---
# from dal_select2.widgets import ModelSelect2Multiple 
# from dal import autocomplete
# --- --------------------------------- ---

class BookingForm(forms.ModelForm):
    
    class Meta:
        model = Booking
        # ตรวจสอบว่า fields ตรงกับ Model ของคุณ
        fields = [
            'room', 'title', 'chairman', 'department', 'start_time',
            'end_time', 'participant_count', 
            'participants', # <-- 1. ช่องค้นหา
            'external_participants', # <-- 2. ช่องพิมพ์เอง
            'presentation_file',
            'additional_requests', 'attachment', 'description', 'additional_notes', 'status',
        ]
        labels = {
            'room': 'ห้องประชุม',
            'title': 'หัวข้อการประชุม',
            'chairman': 'ประธานในที่ประชุม (ถ้ามี)',
            'department': 'แผนกผู้จอง',
            'start_time': 'วัน/เวลา เริ่มต้น',
            'end_time': 'วัน/เวลา สิ้นสุด',
            'participant_count': 'จำนวนผู้เข้าร่วม (โดยประมาณ)',
            'participants': 'รายชื่อผู้เข้าร่วม (ในระบบ)',
            'external_participants': 'รายชื่อผู้เข้าร่วม (ภายนอก)',
            'presentation_file': 'ไฟล์นำเสนอ (ถ้ามี)',
            'additional_requests': 'คำขอเพิ่มเติม (เช่น กาแฟ, อุปกรณ์พิเศษ)',
            'attachment': 'ไฟล์แนบอื่นๆ (ถ้ามี)',
            'description': 'รายละเอียด/วาระการประชุม',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
            'status': 'สถานะ',
        }
        help_texts = {
            'participants': 'พิมพ์ชื่อ, นามสกุล, หรือ username เพื่อค้นหา (ผู้ใช้ในระบบ)',
            'external_participants': 'สำหรับแขก/คนนอก พิมพ์ชื่อ คั่นด้วยจุลภาค (,) หรือขึ้นบรรทัดใหม่',
            'presentation_file': 'ไฟล์ที่ต้องการเปิดขึ้นจอ (PDF, PPT, Word, Excel)',
            'attachment': 'เอกสารอื่นๆ ที่เกี่ยวข้อง',
            'participant_count': 'ระบุจำนวนคร่าวๆ สำหรับการเตรียมห้อง',
        }
        widgets = {
            'room': forms.HiddenInput(),
            'status': forms.HiddenInput(),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),

            # --- 2. 🟢 แก้ไข Widget: ใช้ SelectMultiple ธรรมดา 🟢 ---
            # แต่เพิ่ม 'class' และ 'data-url' ให้ JS ของเรามาเรียกใช้
            'participants': forms.SelectMultiple(
                attrs={
                    'class': 'form-control select2-ajax-users', # 👈 Class ใหม่
                    'data-url': reverse_lazy('user-autocomplete'), # 👈 บอก JS ว่าจะค้นหาที่ไหน
                    'data-theme': 'bootstrap-5',
                }
            ),
            # --- -------------------------------------------- ---

            'external_participants': forms.Textarea(
                attrs={'rows': 3, 'class':'form-control', 'placeholder': 'คุณสมชาย (PTT)\nคุณสมหญิง (SCG)'}
            ),
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'attachment': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control', 'readonly': True}),
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
        }

    # (โค้ด __init__ ... เหมือนเดิม)
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and 'department' in self.fields:
             try:
                 profile = Profile.objects.get(user=user)
                 if profile.department:
                     self.fields['department'].initial = profile.department
                     self.fields['department'].widget.attrs['readonly'] = True
                     self.fields['department'].widget.attrs['class'] = 'form-control bg-light'
             except Profile.DoesNotExist:
                 pass


class ProfileForm(forms.ModelForm):
     first_name = forms.CharField(label='ชื่อจริง', max_length=150, required=False)
     last_name = forms.CharField(label='นามสกุล', max_length=150, required=False)
     email = forms.EmailField(label='อีเมล', required=False)
     class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'email', 'department', 'phone', 'avatar']
        labels = { 'department': 'แผนก/ฝ่าย', 'phone': 'เบอร์โทรศัพท์ติดต่อ', 'avatar': 'รูปโปรไฟล์', }
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': 'เช่น 081-XXX-XXXX'}),
            'first_name': forms.TextInput(attrs={'class':'form-control'}),
            'last_name': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control'}),
            'avatar': forms.ClearableFileInput(attrs={'class':'form-control'}),
        }
     def __init__(self, *args, **kwargs):
         super().__init__(*args, **kwargs)
         if self.instance and self.instance.user:
             self.fields['first_name'].initial = self.instance.user.first_name
             self.fields['last_name'].initial = self.instance.user.last_name
             self.fields['email'].initial = self.instance.user.email
     def save(self, commit=True):
         profile = super().save(commit=False)
         user = profile.user
         user.first_name = self.cleaned_data['first_name']
         user.last_name = self.cleaned_data['last_name']
         user.email = self.cleaned_data['email']
         if commit:
             user.save()
             profile.save()
         return profile

class CustomPasswordChangeForm(PasswordChangeForm):
     old_password = forms.CharField( label="รหัสผ่านเก่า", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'autofocus': True, 'class':'form-control'}), )
     new_password1 = forms.CharField( label="รหัสผ่านใหม่", widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), strip=False, )
     new_password2 = forms.CharField( label="ยืนยันรหัสผ่านใหม่", strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class':'form-control'}), )

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'building', 'floor', 'capacity', 'equipment_in_room', 'image']
        labels = {
            'name': 'ชื่อห้องประชุม', 'building': 'อาคาร', 'floor': 'ชั้น',
            'capacity': 'ความจุ (คน)', 'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'image': 'รูปภาพห้องประชุม (ถ้ามี)',
        }
        help_texts = {
            'equipment_in_room': 'ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่ เช่น โปรเจคเตอร์, ไวท์บอร์ด',
            'image': 'เลือกไฟล์รูปภาพ .jpg, .png', 'capacity': 'ระบุเป็นตัวเลขเท่านั้น',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'เช่น ห้องประชุม O1-1', 'class':'form-control'}),
            'building': forms.TextInput(attrs={'placeholder': 'เช่น สำนักงาน 1, อาคาร R&D', 'class':'form-control'}),
            'floor': forms.TextInput(attrs={'placeholder': 'เช่น ชั้น 1, ชั้น 5', 'class':'form-control'}),
            'capacity': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'placeholder': 'โปรเจคเตอร์\nไวท์บอร์ด\nชุดเครื่องเสียง\nปลั๊กไฟ', 'class':'form-control'}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class':'form-control'}),
        }