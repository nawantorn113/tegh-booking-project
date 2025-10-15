# booking/views.py
# [ฉบับสมบูรณ์และถูกต้อง 100%]

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from .models import Room, Booking, Profile
from .forms import BookingForm, ProfilePictureForm, CustomPasswordChangeForm, RoomForm

# --- Helper Functions ---
def is_admin(user):
    return user.groups.filter(name='Admin').exists()

def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

# --- Auth & Main Pages ---
def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user); return redirect('dashboard')
        else:
            messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'); return redirect('login')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request); messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว'); return redirect('login')

@login_required
def dashboard_view(request):
    return render(request, 'pages/dashboard.html', {'rooms': Room.objects.all().order_by('name')})

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    form = BookingForm(initial={'room': room})
    context = { 'room': room, 'form': form, 'is_admin_user': is_admin(request.user) }
    return render(request, 'pages/room_calendar.html', context)

@login_required
def history_view(request):
    return render(request, 'pages/history.html', {'my_bookings': Booking.objects.filter(booked_by=request.user)})

# --- API ---
@login_required
def bookings_api(request):
    start = request.GET.get('start'); end = request.GET.get('end'); room_id = request.GET.get('room_id')
    bookings = Booking.objects.filter(start_time__gte=start, end_time__lte=end)
    if room_id: bookings = bookings.filter(room_id=room_id)
    events = []
    for booking in bookings:
        if booking.status == 'APPROVED': color = '#198754'
        elif booking.status == 'PENDING': color = '#ffc107'
        elif booking.status == 'REJECTED': color = '#dc3545'
        elif booking.status == 'CANCELLED': color = '#fd7e14'
        else: color = '#6c757d'
        status_text = booking.get_status_display()
        event_title = f"[{status_text}] {booking.title}\n({booking.booked_by.username})"
        events.append({'id': booking.id, 'title': event_title, 'start': booking.start_time.isoformat(), 'end': booking.end_time.isoformat(), 'color': color, 'borderColor': color})
    return JsonResponse(events, safe=False)

# --- Booking Actions ---
@login_required
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            booking.save()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ")
        else:
            if '__all__' in form.errors:
                for error in form.errors['__all__']: messages.error(request, error)
            for field, error_list in form.errors.items():
                if field != '__all__':
                    for error in error_list: messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('room_calendar', room_id=room.id)

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขการจองนี้"); return redirect('dashboard')
    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, "การจองถูกแก้ไขเรียบร้อยแล้ว")
            return redirect('history')
    else:
        form = BookingForm(instance=booking)
    return render(request, 'pages/edit_booking.html', {'form': form, 'booking': booking})

@login_required
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์ยกเลิกการจองนี้"); return redirect('dashboard')
    if request.method == 'POST':
        booking.status = 'CANCELLED'; booking.save()
        messages.success(request, "การจองได้ถูกยกเลิกเรียบร้อยแล้ว")
        return redirect('room_calendar', room_id=booking.room.id)
    return redirect('dashboard')

# --- Approver Actions ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending_bookings = Booking.objects.filter(status='PENDING')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending_bookings})

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

# --- Admin Managements ---
@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    return render(request, 'pages/rooms.html', {'rooms': Room.objects.all().order_by('name')})

@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "เพิ่มห้องประชุมใหม่เรียบร้อยแล้ว"); return redirect('rooms')
    else: form = RoomForm()
    return render(request, 'pages/room_form.html', {'form': form, 'title': 'เพิ่มห้องประชุมใหม่'})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid(): form.save(); messages.success(request, "แก้ไขข้อมูลห้องประชุมเรียบร้อยแล้ว"); return redirect('rooms')
    else: form = RoomForm(instance=room)
    return render(request, 'pages/room_form.html', {'form': form, 'title': f'แก้ไข: {room.name}'})

@login_required
@user_passes_test(is_admin)
def delete_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST': room.delete(); messages.success(request, f"ห้อง '{room.name}' ถูกลบออกจากระบบแล้ว")
    return redirect('rooms')

# --- Other Pages ---
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

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    room_usage_stats = Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__status='APPROVED'))).order_by('-booking_count')
    department_stats = Booking.objects.filter(status='APPROVED').exclude(department__exact='').values('department').annotate(count=Count('id')).order_by('-count')
    context = {'room_usage_stats': room_usage_stats, 'department_stats': department_stats,}
    return render(request, 'pages/reports.html', context)