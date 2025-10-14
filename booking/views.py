# booking/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Room, Booking, Profile
from .forms import BookingForm, ProfilePictureForm, CustomPasswordChangeForm

# --- Views สำหรับ Auth (เหมือนเดิม) ---
def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
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

# --- [แก้ไข] Views สำหรับแต่ละหน้า (Page) พร้อมข้อมูล ---

@login_required
def dashboard_view(request):
    # [แก้ไข] ดึงข้อมูลห้องประชุมทั้งหมดมาส่งให้ Template
    rooms = Room.objects.all().order_by('location', 'name')
    context = {'rooms': rooms}
    return render(request, 'pages/dashboard.html', context)

@login_required
def history_view(request):
    # [แก้ไข] ดึงข้อมูลการจองเฉพาะของผู้ใช้ที่ login อยู่
    my_bookings = Booking.objects.filter(booked_by=request.user)
    context = {'my_bookings': my_bookings}
    return render(request, 'pages/history.html', context)

def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    # [แก้ไข] ดึงข้อมูลการจองที่รออนุมัติ
    pending_bookings = Booking.objects.filter(status='PENDING')
    context = {'pending_bookings': pending_bookings}
    return render(request, 'pages/approvals.html', context)

# ... โค้ดส่วนที่เหลือ (create_booking, approve, reject, edit_profile) ยังคงเหมือนเดิม ...
@login_required
def create_booking_view(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False); booking.booked_by = request.user; booking.save(); form.save_m2m()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ"); return redirect('dashboard')
    else: form = BookingForm()
    return render(request, 'create_booking.html', {'form': form})

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id); booking.status = 'APPROVED'; booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว"); return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id); booking.status = 'REJECTED'; booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ"); return redirect('approvals')

@login_required
def edit_profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save(); update_session_auth_hash(request, user); messages.success(request, 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว'); return redirect('edit_profile')
            else: picture_form = ProfilePictureForm(instance=profile)
        elif 'change_picture' in request.POST:
            picture_form = ProfilePictureForm(request.POST, request.FILES, instance=profile)
            if picture_form.is_valid():
                picture_form.save(); messages.success(request, 'อัปเดตรูปโปรไฟล์เรียบร้อยแล้ว'); return redirect('edit_profile')
            else: password_form = CustomPasswordChangeForm(request.user)
    else:
        picture_form = ProfilePictureForm(instance=profile); password_form = CustomPasswordChangeForm(request.user)
    return render(request, 'pages/edit_profile.html', {'picture_form': picture_form, 'password_form': password_form})

def is_admin(user): return user.groups.filter(name='Admin').exists()

@login_required
@user_passes_test(is_admin)
def room_management_view(request): return render(request, 'pages/rooms.html')
@login_required
@user_passes_test(is_admin)
def user_management_view(request): return render(request, 'pages/users.html')
@login_required
@user_passes_test(is_admin)
def reports_view(request): return render(request, 'pages/reports.html')
@login_required
@user_passes_test(is_admin)
def settings_view(request): return render(request, 'pages/settings.html')