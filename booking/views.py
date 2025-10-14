# booking/views.py
# [แก้ไข] แก้ไขการจัดย่อหน้า (Indentation) และอักขระพิเศษทั้งหมด

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Room, Booking, Profile
from .forms import BookingForm, ProfilePictureForm, CustomPasswordChangeForm

# --- 1. Views สำหรับ Auth & Pages ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
            return redirect('login')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว')
    return redirect('login')

@login_required
def dashboard_view(request):
    rooms = Room.objects.all().order_by('location', 'name')
    context = {'rooms': rooms}
    return render(request, 'pages/dashboard.html', context)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    form = BookingForm() # สร้างฟอร์มเปล่าเพื่อส่งไปให้ Modal
    context = {
        'room': room,
        'form': form
    }
    return render(request, 'pages/room_calendar.html', context)

@login_required
def history_view(request):
    my_bookings = Booking.objects.filter(booked_by=request.user)
    context = {'my_bookings': my_bookings}
    return render(request, 'pages/history.html', context)

def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending_bookings = Booking.objects.filter(status='PENDING')
    context = {'pending_bookings': pending_bookings}
    return render(request, 'pages/approvals.html', context)

# --- 2. API Views ---
@login_required
def bookings_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    room_id = request.GET.get('room_id')
    bookings = Booking.objects.filter(start_time__gte=start, end_time__lte=end).exclude(status='REJECTED')
    if room_id:
        bookings = bookings.filter(room_id=room_id)
    events = []
    for booking in bookings:
        if booking.status == 'APPROVED': color = '#0d6efd'
        elif booking.status == 'PENDING': color = '#ffc107'
        else: color = '#6c757d'
        events.append({
            'id': booking.id,
            'title': f"{booking.title}\n({booking.booked_by.username})",
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'color': color,
            'borderColor': color,
        })
    return JsonResponse(events, safe=False)

# --- 3. Action Views ---
@login_required
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            booking.room = room
            booking.save()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    return redirect('room_calendar', room_id=room.id)

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    return redirect('approvals')

# --- 4. Profile & Admin Placeholder Views ---
@login_required
def edit_profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว')
                return redirect('edit_profile')
            else:
                picture_form = ProfilePictureForm(instance=profile)
        elif 'change_picture' in request.POST:
            picture_form = ProfilePictureForm(request.POST, request.FILES, instance=profile)
            if picture_form.is_valid():
                picture_form.save()
                messages.success(request, 'อัปเดตรูปโปรไฟล์เรียบร้อยแล้ว')
                return redirect('edit_profile')
            else:
                password_form = CustomPasswordChangeForm(request.user)
    else:
        picture_form = ProfilePictureForm(instance=profile)
        password_form = CustomPasswordChangeForm(request.user)
    context = {'picture_form': picture_form, 'password_form': password_form}
    return render(request, 'pages/edit_profile.html', context)

def is_admin(user):
    return user.groups.filter(name='Admin').exists()

@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    return render(request, 'pages/rooms.html')