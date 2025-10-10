from django import forms
from .models import Booking
from django.utils import timezone

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['room', 'title', 'start_time', 'end_time']
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'end_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time:
            if start_time < timezone.now():
                raise forms.ValidationError("ไม่สามารถจองเวลาย้อนหลังได้")
            if end_time <= start_time:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น")

            room = cleaned_data.get("room")
            conflicting_bookings = Booking.objects.filter(
                room=room,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exclude(status='REJECTED')

            if self.instance.pk:
                conflicting_bookings = conflicting_bookings.exclude(pk=self.instance.pk)

            if conflicting_bookings.exists():
                raise forms.ValidationError(f"ห้อง '{room.name}' ไม่ว่างในช่วงเวลานี้ กรุณาเลือกเวลาอื่น")

        return cleaned_data