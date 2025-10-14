from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Room, Booking
from .forms import BookingForm

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
    return redirect('login')

@login_required
def dashboard_view(request):
    my_bookings = Booking.objects.filter(booked_by=request.user).order_by('-start_time')
    rooms = Room.objects.all().order_by('name')
    is_admin = request.user.groups.filter(name='Admin').exists()
    is_approver = request.user.groups.filter(name='Approver').exists()
    context = {
        'my_bookings': my_bookings,
        'rooms': rooms,
        'is_admin': is_admin,
        'is_approver': is_approver,
    }
    if is_admin or is_approver:
        context['pending_bookings'] = Booking.objects.filter(status='PENDING')
    return render(request, 'dashboard.html', context)

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

def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    return redirect('dashboard')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    return redirect('dashboard')