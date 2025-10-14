from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Room, Booking
from .forms import BookingForm

# --- 1. Views สำหรับ Auth (เหมือนเดิม) ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
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

# --- 2. [ใหม่] Views สำหรับแต่ละหน้า (Page) ---

@login_required
def dashboard_view(request):
    # หน้านี้จะแสดงข้อมูลห้องประชุมทั้งหมด
    rooms = Room.objects.all().order_by('location', 'name')
    return render(request, 'pages/dashboard.html', {'rooms': rooms})

@login_required
def history_view(request):
    # หน้านี้จะแสดงประวัติการจองของผู้ใช้ที่ login อยู่
    my_bookings = Booking.objects.filter(booked_by=request.user)
    return render(request, 'pages/history.html', {'my_bookings': my_bookings})

def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    # หน้านี้จะแสดงรายการที่รออนุมัติ
    pending_bookings = Booking.objects.filter(status='PENDING')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending_bookings})

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Admin').exists())
def room_management_view(request):
    # ในอนาคต หน้านี้จะใช้สำหรับจัดการห้อง (ตอนนี้แสดงแค่ placeholder)
    return render(request, 'pages/rooms.html')

# --- 3. Views สำหรับจัดการการจอง (ส่วนใหญ่เหมือนเดิม) ---

@login_required
def create_booking_view(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            booking.save()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ")
            return redirect('dashboard')
    else:
        form = BookingForm()
    return render(request, 'create_booking.html', {'form': form})

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    return redirect('approvals') # กลับไปหน้ารออนุมัติ

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    return redirect('approvals') # กลับไปหน้ารออนุมัติ