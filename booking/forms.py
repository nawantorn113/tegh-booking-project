from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Booking, Profile, Room # ตรวจสอบว่า import Room ถูกต้อง
from django.contrib.auth.models import User

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'description', 'start_time', 'end_time',
            'participant_count', 'participants', 'status', # สังเกต: ปกติ status ไม่ควรให้ User แก้ไขเอง อาจต้องเอาออก
            'additional_requests', 'attachment', 'chairman', 'additional_notes'
        ]
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
             # Widget สำหรับ participants ควรใช้ Select2 หรือ Autocomplete widget อื่นๆ
             # forms.SelectMultiple ไม่ค่อยเหมาะถ้า user มีจำนวนมาก
             'participants': forms.SelectMultiple(attrs={'class': 'select2 form-control', 'data-placeholder': 'เลือกผู้เข้าร่วม'}),
             'description': forms.Textarea(attrs={'rows': 3}),
             'additional_requests': forms.Textarea(attrs={'rows': 3}),
             'additional_notes': forms.Textarea(attrs={'rows': 3}),
             # อาจจะต้องซ่อน Field 'room' ใน Template เพราะมักจะกำหนดค่ามาจาก URL
             'room': forms.HiddenInput(),
             # ซ่อน Field 'status' ถ้าไม่ต้องการให้ user แก้ไข
             'status': forms.HiddenInput(),
        }
        labels = {
            'room': 'ห้องประชุม',
            'title': 'หัวข้อการประชุม',
            'description': 'รายละเอียด',
            'start_time': 'เวลาเริ่มต้น',
            'end_time': 'เวลาสิ้นสุด',
            'participant_count': 'จำนวนผู้เข้าร่วม (โดยประมาณ)',
            'participants': 'รายชื่อผู้เข้าร่วม (ถ้ามี)',
            'status': 'สถานะ',
            'additional_requests': 'คำขอเพิ่มเติม (เช่น กาแฟ, อุปกรณ์)',
            'attachment': 'ไฟล์แนบ (เช่น เอกสารประกอบ)',
            'chairman': 'ประธานในที่ประชุม (ถ้ามี)',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
        }
        help_texts = {
            'participants': 'เลือก User ที่จะเข้าร่วมประชุมด้วย',
            'attachment': 'แนบไฟล์ PDF, Word, Excel หรืออื่นๆ ที่เกี่ยวข้อง',
        }

class ProfileForm(forms.ModelForm):
     # เพิ่ม Field สำหรับ User model เข้ามาแก้ไขพร้อมกัน
     first_name = forms.CharField(label='ชื่อจริง', max_length=150, required=False)
     last_name = forms.CharField(label='นามสกุล', max_length=150, required=False)
     email = forms.EmailField(label='อีเมล', required=False)

     class Meta:
        model = Profile
        # fields = ['department', 'phone', 'avatar'] # เอา field User มารวม
        fields = ['first_name', 'last_name', 'email', 'department', 'phone', 'avatar']
        labels = {
            'department': 'แผนก/ฝ่าย',
            'phone': 'เบอร์โทรศัพท์ติดต่อ',
            'avatar': 'รูปโปรไฟล์',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': 'เช่น 081-XXX-XXXX'}),
        }

     # ต้อง override __init__ เพื่อดึงค่าเริ่มต้นของ User มาใส่
     def __init__(self, *args, **kwargs):
         super().__init__(*args, **kwargs)
         # ถ้าเป็นการแก้ไข (มี instance) ให้ดึงค่าจาก user มาใส่
         if self.instance and self.instance.user:
             self.fields['first_name'].initial = self.instance.user.first_name
             self.fields['last_name'].initial = self.instance.user.last_name
             self.fields['email'].initial = self.instance.user.email

     # ต้อง override save เพื่อบันทึกข้อมูล User ด้วย
     def save(self, commit=True):
         profile = super().save(commit=False)
         user = profile.user
         user.first_name = self.cleaned_data['first_name']
         user.last_name = self.cleaned_data['last_name']
         user.email = self.cleaned_data['email'] # ควรมีการตรวจสอบ email ซ้ำใน view
         if commit:
             user.save()
             profile.save()
         return profile


class CustomPasswordChangeForm(PasswordChangeForm):
    # ปรับ Label ให้เป็นภาษาไทย (ถ้าต้องการ)
     old_password = forms.CharField(
         label="รหัสผ่านเก่า",
         strip=False,
         widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'autofocus': True}),
     )
     new_password1 = forms.CharField(
         label="รหัสผ่านใหม่",
         widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
         strip=False,
     )
     new_password2 = forms.CharField(
         label="ยืนยันรหัสผ่านใหม่",
         strip=False,
         widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
     )


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        # --- 🟢 แก้ไข: ใช้ชื่อ Field ภาษาอังกฤษ 🟢 ---
        fields = ['name', 'building', 'floor', 'capacity', 'equipment_in_room', 'image']
        # --- ------------------------------------ ---

        # --- ✅ เพิ่ม: กำหนด Label ภาษาไทย ✅ ---
        labels = {
            'name': 'ชื่อห้องประชุม',
            'building': 'อาคาร',
            'floor': 'ชั้น',
            'capacity': 'ความจุ (คน)',
            'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'image': 'รูปภาพห้องประชุม (ถ้ามี)',
        }
        # --- ----------------------------- ---

        help_texts = {
            'equipment_in_room': 'ระบุอุปกรณ์แต่ละอย่างในบรรทัดใหม่ เช่น โปรเจคเตอร์, ไวท์บอร์ด',
            'image': 'เลือกไฟล์รูปภาพ .jpg, .png',
            'capacity': 'ระบุเป็นตัวเลขเท่านั้น',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': ''}),
            'building': forms.TextInput(attrs={'placeholder': ''}),
            'floor': forms.TextInput(attrs={'placeholder': ''}),
            'capacity': forms.NumberInput(attrs={'min': '1'}),
            'equipment_in_room': forms.Textarea(attrs={'rows': 5, 'placeholder': ''}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}), # จำกัดให้รับเฉพาะไฟล์รูปภาพ
        }