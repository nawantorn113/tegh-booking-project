from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Booking, Profile, Room
from django.contrib.auth.models import User

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'room', 'title', 'description', 'start_time', 'end_time',
            'participant_count', 'participants', 'status',
            'additional_requests', 'attachment', 'chairman', 'additional_notes'
        ]
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'participants': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['department', 'phone', 'avatar']


class CustomPasswordChangeForm(PasswordChangeForm):
    # ใช้ PasswordChangeForm เดิมของ Django
    pass


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'building', 'floor', 'capacity', 'equipment_in_room', 'image']
