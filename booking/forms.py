# booking/forms.py
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Booking, Profile, Room # ตรวจสอบว่า import Room ถูกต้อง
from django.contrib.auth.models import User
# สำหรับ Autocomplete (ถ้าใช้)
# from dal import autocomplete

class BookingForm(forms.ModelForm):
    # ถ้า department ไม่ได้อยู่ใน Booking model แต่ดึงจาก Profile
    # department = forms.CharField(label="แผนก", max_length=100, required=False, disabled=True)

    class Meta:
        model = Booking
        fields = [
            'room', # ซ่อนไว้
            'title',
            'chairman', # เพิ่มเข้ามา
            'department', # ใช้ชื่อ field ที่ถูกต้องจาก models.py
            'start_time',
            'end_time',
            'participant_count',
            'participants',
            'presentation_file', # เพิ่มเข้ามา
            'additional_requests',
            'attachment', # อาจจะใช้ชื่อนี้สำหรับไฟล์แนบทั่วไป
            'description', # ย้ายมาท้ายๆ
            'additional_notes', # ย้ายมาท้ายๆ
            'status', # ซ่อนไว้
        ]
        labels = {
            'room': 'ห้องประชุม',
            'title': 'หัวข้อการประชุม',
            'chairman': 'ประธานในที่ประชุม (ถ้ามี)',
            'department': 'แผนกผู้จอง',
            'start_time': 'วัน/เวลา เริ่มต้น', # เปลี่ยน Label
            'end_time': 'วัน/เวลา สิ้นสุด', # เปลี่ยน Label
            'participant_count': 'จำนวนผู้เข้าร่วม (โดยประมาณ)',
            'participants': 'รายชื่อผู้เข้าร่วม (เลือกจากระบบ)',
            'presentation_file': 'ไฟล์นำเสนอ (ถ้ามี)', # เปลี่ยน Label
            'additional_requests': 'คำขอเพิ่มเติม (เช่น กาแฟ, อุปกรณ์พิเศษ)',
            'attachment': 'ไฟล์แนบอื่นๆ (ถ้ามี)',
            'description': 'รายละเอียด/วาระการประชุม',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
            'status': 'สถานะ',
        }
        help_texts = {
            'participants': 'พิมพ์ชื่อเพื่อค้นหาและเลือกผู้เข้าร่วม',
            'presentation_file': 'ไฟล์ที่ต้องการเปิดขึ้นจอ (PDF, PPT, Word, Excel)',
            'attachment': 'เอกสารอื่นๆ ที่เกี่ยวข้อง',
            'participant_count': 'ระบุจำนวนคร่าวๆ สำหรับการเตรียมห้อง',
        }
        widgets = {
            'room': forms.HiddenInput(),
            'status': forms.HiddenInput(),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}), # เพิ่ม class
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}), # เพิ่ม class
            # ใช้ Autocomplete widget สำหรับ participants (ต้อง setup URL และ View ด้วย)
            'participants': forms.SelectMultiple(attrs={'class': 'select2 form-control', 'data-placeholder': 'เลือกผู้เข้าร่วม (พิมพ์เพื่อค้นหา)'}),
            # ใช้ Textarea สำหรับช่องยาวๆ
            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            # ใช้ FileInput สำหรับไฟล์
            'presentation_file': forms.ClearableFileInput(attrs={'class':'form-control'}),
            'attachment': forms.ClearableFileInput(attrs={'class':'form-control'}),
            # ใส่ class ให้ Field อื่นๆ ด้วย (ถึงแม้ JS จะใส่อยู่แล้วก็ตาม)
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            'department': forms.TextInput(attrs={'class':'form-control', 'readonly': True}), # ถ้าดึงมาจาก Profile ให้ readonly
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
        }

    # Override __init__ ถ้าต้องการดึงค่า Department จาก Profile มาแสดง
    def __init__(self, *args, **kwargs):
        # ดึง user ออกมาก่อน gọi super
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ตั้งค่า Department เริ่มต้น (ถ้ามี user และ field department)
        if user and 'department' in self.fields:
             try:
                 # ดึงค่า department จาก Profile ของ user
                 profile = Profile.objects.get(user=user)
                 if profile.department:
                     self.fields['department'].initial = profile.department
                     # ทำให้ field อ่านได้อย่างเดียว ถ้าดึงมาจาก Profile
                     self.fields['department'].widget.attrs['readonly'] = True
                     self.fields['department'].widget.attrs['class'] = 'form-control bg-light' # ทำให้ดูเหมือน disabled
             except Profile.DoesNotExist:
                 pass # ไม่มี Profile ก็ไม่ต้องทำอะไร

        # (Optional) จำกัด choices ของ participants ถ้าต้องการ
        # self.fields['participants'].queryset = User.objects.filter(is_active=True).exclude(pk=user.pk if user else None)

# --- RoomForm, ProfileForm, CustomPasswordChangeForm เหมือนเดิม ---
# (ตรวจสอบให้แน่ใจว่า RoomForm ใช้ fields ภาษาอังกฤษและมี labels ภาษาไทยแล้ว)

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
             # self.save_m2m() # Important if Profile has M2M fields later
         return profile


class CustomPasswordChangeForm(PasswordChangeForm):
    # ปรับ Label ให้เป็นภาษาไทย (ถ้าต้องการ)
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


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        # --- ใช้ชื่อ Field ภาษาอังกฤษ ---
        fields = ['name', 'building', 'floor', 'capacity', 'equipment_in_room', 'image']
        # --- ------------------------ ---

        # --- กำหนด Label ภาษาไทย ---
        labels = {
            'name': 'ชื่อห้องประชุม',
            'building': 'อาคาร',
            'floor': 'ชั้น',
            'capacity': 'ความจุ (คน)',
            'equipment_in_room': 'อุปกรณ์ภายในห้อง',
            'image': 'รูปภาพห้องประชุม (ถ้ามี)',
        }
        # --- --------------------- ---

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
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*', 'class':'form-control'}),
        }