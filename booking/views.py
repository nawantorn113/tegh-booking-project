# booking/views.py
# [ฉบับสมบูรณ์ล่าสุด 16/10/2025 - เพิ่ม Master Calendar]

import json
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User, Group
from dal_select2.views import Select2QuerySetView
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from openpyxl import Workbook
from django.utils import timezone
from .models import Room, Booking, Profile
from .forms import BookingForm, ProfilePictureForm, CustomPasswordChangeForm, RoomForm

# --- Helper Functions ---
def send_booking_notification(booking, template_name, subject, recipient_list):
    if not recipient_list:
        return
    context = {'booking': booking}
    message = render_to_string(template_name, context)
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list, fail_silently=False)
    except Exception as e:
        print(f"Error sending email: {e}")

def get_admin_emails():
    admins_and_approvers = User.objects.filter(groups__name__in=['Admin', 'Approver'], is_active=True)
    return [user.email for user in admins_and_approvers if user.email]

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return User.objects.none()
        qs = User.objects.all().order_by('first_name')
        if self.q:
            qs = qs.filter(Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q))
        return qs

def is_admin(user):
    return user.is_authenticated and user.groups.filter(name='Admin').exists()

def is_approver_or_admin(user):
    return user.is_authenticated and user.groups.filter(name__in=['Approver', 'Admin']).exists()

# --- Auth & Main Pages ---
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
    now = timezone.now()
    today = now.date()
    all_rooms = Room.objects.all().order_by('name')
    for room in all_rooms:
        current_booking = Booking.objects.filter(
            room=room, start_time__lte=now, end_time__gt=now, status='APPROVED'
        ).first()
        room.status = 'ไม่ว่าง' if current_booking else 'ว่าง'
        room.current_booking_title = current_booking.title if current_booking else None
    
    summary_cards = {
        'total_rooms': all_rooms.count(),
        'today_bookings': Booking.objects.filter(start_time__date=today, status='APPROVED').count(),
        'pending_approvals': Booking.objects.filter(status='PENDING').count(),
    }
    context = {'rooms': all_rooms, 'summary_cards': summary_cards}
    return render(request, 'pages/dashboard.html', context)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    form = BookingForm(initial={'room': room})
    context = {'room': room, 'form': form, 'is_admin_user': is_admin(request.user)}
    return render(request, 'pages/room_calendar.html', context)

@login_required
def master_calendar_view(request):
    return render(request, 'pages/master_calendar.html')

@login_required
def history_view(request):
    my_bookings = Booking.objects.filter(booked_by=request.user).order_by('-start_time')
    query_date = request.GET.get('date')
    query_room = request.GET.get('room')
    query_status = request.GET.get('status')
    if query_date: my_bookings = my_bookings.filter(start_time__date=query_date)
    if query_room: my_bookings = my_bookings.filter(room__id=query_room)
    if query_status: my_bookings = my_bookings.filter(status=query_status)
    context = {
        'my_bookings': my_bookings, 'all_rooms': Room.objects.all().order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
    }
    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if (booking.booked_by != request.user and not is_admin(request.user) and request.user not in booking.participants.all()):
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")
        return redirect('dashboard')
    return render(request, 'pages/booking_detail.html', {'booking': booking})

# --- API Views ---
@login_required
def bookings_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    room_id = request.GET.get('room_id')
    
    if room_id:
        bookings = Booking.objects.filter(room_id=room_id, start_time__gte=start, end_time__lte=end)
    else:
        bookings = Booking.objects.filter(start_time__gte=start, end_time__lte=end)

    events = []
    for booking in bookings:
        color_map = {'APPROVED': '#198754', 'PENDING': '#ffc107', 'REJECTED': '#dc3545', 'CANCELLED': '#fd7e14'}
        color = color_map.get(booking.status, '#6c757d')
        event_title = f"[{booking.get_status_display()}] {booking.title}\n({booking.booked_by.username})"
        events.append({
            'id': booking.id,
            'title': event_title,
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'color': color,
            'borderColor': color,
            'extendedProps': {
                'room_id': booking.room.id,
                'room_name': booking.room.name
            }
        })
    return JsonResponse(events, safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, pk=data.get('booking_id'))
        if booking.booked_by != request.user and not is_admin(request.user):
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        new_start = datetime.fromisoformat(data.get('start_time').replace('Z', '+00:00'))
        new_end = datetime.fromisoformat(data.get('end_time').replace('Z', '+00:00'))
        conflicts = Booking.objects.filter(room=booking.room, start_time__lt=new_end, end_time__gt=new_start).exclude(pk=booking.id).exclude(status__in=['REJECTED', 'CANCELLED'])
        if conflicts.exists():
            return JsonResponse({'status': 'error', 'message': 'ช่วงเวลาที่เลือกไม่ว่าง'}, status=400)
        booking.start_time = new_start
        booking.end_time = new_end
        booking.save()
        admin_emails = get_admin_emails()
        send_booking_notification(booking, 'emails/booking_changed_alert.txt', f"[เปลี่ยนเวลา] {booking.title}", admin_emails)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# --- Booking Action Views ---
@login_required
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            booking.save()
            form.save_m2m()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ")
            admin_emails = get_admin_emails()
            send_booking_notification(booking, 'emails/new_booking_alert.txt', f"[จองห้องใหม่] {booking.title}", admin_emails)
        else:
            if '__all__' in form.errors:
                for error in form.errors['__all__']:
                    messages.error(request, error)
            for field, error_list in form.errors.items():
                if field != '__all__':
                    for error in error_list:
                        messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('room_calendar', room_id=room.id)

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขการจองนี้")
        return redirect('dashboard')
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            updated_booking = form.save()
            messages.success(request, "การจองถูกแก้ไขเรียบร้อยแล้ว")
            admin_emails = get_admin_emails()
            send_booking_notification(updated_booking, 'emails/booking_changed_alert.txt', f"[แก้ไขการจอง] {updated_booking.title}", admin_emails)
            return redirect('history')
    else:
        form = BookingForm(instance=booking)
    return render(request, 'pages/edit_booking.html', {'form': form, 'booking': booking})

@login_required
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์ยกเลิกการจองนี้")
        return redirect('dashboard')
    if request.method == 'POST':
        booking.status = 'CANCELLED'
        booking.save()
        messages.success(request, "การจองได้ถูกยกเลิกเรียบร้อยแล้ว")
        admin_emails = get_admin_emails()
        send_booking_notification(booking, 'emails/booking_cancelled_alert.txt', f"[ยกเลิกการจอง] {booking.title}", admin_emails)
        return redirect('room_calendar', room_id=booking.room.id)
    return redirect('dashboard')

# --- Approver Views ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending_bookings = Booking.objects.filter(status='PENDING')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending_bookings})

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    if booking.booked_by.email:
        send_booking_notification(booking, 'emails/booking_status_update.txt', f"สถานะการจอง: '{booking.title}' ได้รับการอนุมัติแล้ว", [booking.booked_by.email])
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    if booking.booked_by.email:
        send_booking_notification(booking, 'emails/booking_status_update.txt', f"สถานะการจอง: '{booking.title}' ถูกปฏิเสธ", [booking.booked_by.email])
    return redirect('approvals')

# --- Admin Views ---
@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    users = User.objects.all().order_by('username').prefetch_related('groups')
    return render(request, 'pages/user_management.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    user_to_edit = get_object_or_404(User, pk=user_id)
    all_groups = Group.objects.all()
    if request.method == 'POST':
        user_to_edit.groups.clear()
        group_ids = request.POST.getlist('groups')
        for group_id in group_ids:
            group = Group.objects.get(pk=group_id)
            user_to_edit.groups.add(group)
        messages.success(request, f"อัปเดตสิทธิ์ของผู้ใช้ '{user_to_edit.username}' เรียบร้อยแล้ว")
        return redirect('user_management')
    context = {'user_to_edit': user_to_edit, 'all_groups': all_groups}
    return render(request, 'pages/edit_user_roles.html', context)

@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    return render(request, 'pages/rooms.html', {'rooms': Room.objects.all().order_by('name')})

@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มห้องประชุมใหม่เรียบร้อยแล้ว")
            return redirect('rooms')
    else:
        form = RoomForm()
    return render(request, 'pages/room_form.html', {'form': form, 'title': 'เพิ่มห้องประชุมใหม่'})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "แก้ไขข้อมูลห้องประชุมเรียบร้อยแล้ว")
            return redirect('rooms')
    else:
        form = RoomForm(instance=room)
    return render(request, 'pages/room_form.html', {'form': form, 'title': f'แก้ไข: {room.name}'})

@login_required
@user_passes_test(is_admin)
def delete_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        room.delete()
        messages.success(request, f"ห้อง '{room.name}' ถูกลบออกจากระบบแล้ว")
    return redirect('rooms')

@login_required
def reports_view(request):
    room_usage_stats = Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__status='APPROVED'))).order_by('-booking_count')
    context = {'room_usage_stats': room_usage_stats, 'department_stats': []}
    return render(request, 'pages/reports.html', context)

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="booking_reports.xlsx"'
    workbook = Workbook()
    ws1 = workbook.active
    ws1.title = "Room Usage"
    ws1.append(['ชื่อห้องประชุม', 'จำนวนครั้งที่ใช้งาน (อนุมัติแล้ว)'])
    room_stats = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__status='APPROVED'))).order_by('-count')
    for room in room_stats:
        ws1.append([room.name, room.count])
    workbook.save(response)
    return response

# --- Profile View ---
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
    return render(request, 'pages/edit_profile.html', {'picture_form': picture_form, 'password_form': password_form})