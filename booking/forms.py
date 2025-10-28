# booking/forms.py
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
# 1. ลบ 'Profile' และ 'Equipment' ออกจาก import นี้
from .models import Booking, Room 
from django.contrib.auth.models import User
from django.urls import reverse_lazy 

# 2. เพิ่ม Import นี้ (สำหรับช่องค้นหา)
from dal import autocomplete

class BookingForm(forms.ModelForm):
    
    # 3. เพิ่ม Field ใหม่ (สำหรับอัปโหลดหลายไฟล์)
    attachments = forms.FileField(
        label="ไฟล์แนบ (สูงสุด 8 ไฟล์)",
        required=False,
        widget=forms.ClearableFileInput(attrs={ # 👈 ใช้ ClearableFileInput
            'class': 'form-control'
        })
    )

    class Meta:
        model = Booking
        # 4. ลบ 'equipment' และ 'external_participants'
        fields = [
            'room', 'title', 'chairman', 'department', 'start_time',
            'end_time', 'participant_count', 
            'participants', 
            'description', 'additional_requests', 'additional_notes', 'status',
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
            'presentation_file': 'ไฟล์นำเสนอ (ถ้ามี)',
            'description': 'รายละเอียด/วาระการประชุม',
            'additional_requests': 'คำขอเพิ่มเติม (เช่น กาแฟ, อุปกรณ์พิเศษ)',
            'additional_notes': 'หมายเหตุเพิ่มเติม',
            'status': 'สถานะ',
        }
        help_texts = {
            'participants': 'พิมพ์ชื่อ, นามสกุล, หรือ username เพื่อค้นหา (ผู้ใช้ในระบบ)',
            'participant_count': 'ระบุจำนวนคร่าวๆ สำหรับการเตรียมห้อง',
        }
        widgets = {
            'room': forms.HiddenInput(),
            'status': forms.HiddenInput(),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class':'form-control'}),

            # 5. ใช้ Widget ของ 'dal' (django-autocomplete-light)
            'participants': autocomplete.ModelSelect2Multiple(
                url='user-autocomplete',
                attrs={'data-placeholder': 'พิมพ์เพื่อค้นหา...', 'data-theme': 'bootstrap-5'}
            ),
            
            # (ลบ Widget ของ equipment ออก)

            'description': forms.Textarea(attrs={'rows': 3, 'class':'form-control'}),
            'additional_requests': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 2, 'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'chairman': forms.TextInput(attrs={'class':'form-control'}),
            
            # 6. ทำให้ช่อง Department กรอกได้เอง
            'department': forms.TextInput(attrs={'class':'form-control', 'placeholder': 'เช่น IT, HR, บัญชี'}),
            
            'participant_count': forms.NumberInput(attrs={'min': '1', 'class':'form-control'}),
        }

    # 7. ลบ __init__ ที่ผูกกับ Profile/Equipment ออก
    def __init__(self, *args, **kwargs):
        # (ลบ user = kwargs.pop('user', None))
        super().__init__(*args, **kwargs)
        # (ลบ Logic ที่เกี่ยวกับ Profile/Department/Equipment ออก)


# (ลบ Class ProfileForm ทั้งหมด)

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