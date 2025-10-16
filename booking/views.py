# booking/views.py
# [ฉบับสมบูรณ์]

import json
from datetime import datetime, timedelta
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
from django.template.loader import render_to_string, get_template
from django.conf import settings
from openpyxl import Workbook
from django.utils import timezone
from weasyprint import HTML
from collections import defaultdict
from .models import Room, Booking, Profile, LoginHistory
from .forms import BookingForm, ProfileForm, CustomPasswordChangeForm, RoomForm
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

# --- ระบบบันทึกประวัติการเข้าระบบ ---
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    LoginHistory.objects.create(user=user, action='LOGIN')

@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    if user and user.is_authenticated:
        LoginHistory.objects.create(user=user, action='LOGOUT')

# --- Helper Functions ---
def send_booking_notification(booking, template_name, subject, recipient_list):
    if not recipient_list: return
    context = {'booking': booking}
    message = render_to_string(template_name, context)
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list, fail_silently=False)
    except Exception as e: print(f"Error sending email: {e}")

def get_admin_emails():
    admins_and_approvers = User.objects.filter(groups__name__in=['Admin', 'Approver'], is_active=True)
    return [user.email for user in admins_and_approvers if user.email]

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.all().order_by('username')
        if self.q: qs = qs.filter(Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q))
        return qs

def is_admin(user):
    return user.is_authenticated and user.groups.filter(name='Admin').exists()

def is_approver_or_admin(user):
    return user.is_authenticated and user.groups.filter(name__in=['Approver', 'Admin']).exists()

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
    user_before_logout = request.user
    logout(request)
    # Manually trigger the logout signal after logout completes
    user_logged_out.send(sender=user_before_logout.__class__, request=request, user=user_before_logout)
    messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว'); return redirect('login')

@login_required
def dashboard_view(request):
    now = timezone.now(); sort_by = request.GET.get('sort', 'floor')
    all_rooms = Room.objects.all()
    if sort_by == 'status': all_rooms = sorted(all_rooms, key=lambda r: not r.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').exists())
    elif sort_by == 'capacity': all_rooms = sorted(all_rooms, key=lambda r: r.capacity, reverse=True)
    elif sort_by == 'name': all_rooms = all_rooms.order_by('name')
    else: all_rooms = all_rooms.order_by('building', 'floor', 'name')
    buildings = defaultdict(list)
    for room in all_rooms:
        current_booking = room.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').first()
        if current_booking:
            room.status, room.current_booking_info, room.next_booking_info = 'ไม่ว่าง', current_booking, None
        else:
            room.status, room.current_booking_info = 'ว่าง', None
            room.next_booking_info = room.bookings.filter(start_time__gt=now, status='APPROVED').order_by('start_time').first()
        room.equipment_list = [eq.strip() for eq in room.equipment_in_room.split('\n') if eq.strip()]
        buildings[room.building].append(room)
    summary_cards = {
        'total_rooms': Room.objects.count(),
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': Booking.objects.filter(status='PENDING').count(),
    }
    context = {'buildings': dict(buildings), 'summary_cards': summary_cards, 'current_sort': sort_by}
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
    if request.GET.get('date'): my_bookings = my_bookings.filter(start_time__date=request.GET.get('date'))
    if request.GET.get('room'): my_bookings = my_bookings.filter(room__id=request.GET.get('room'))
    if request.GET.get('status'): my_bookings = my_bookings.filter(status=request.GET.get('status'))
    context = {'my_bookings': my_bookings, 'all_rooms': Room.objects.all().order_by('name'), 'status_choices': Booking.STATUS_CHOICES}
    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if (booking.booked_by != request.user and not is_admin(request.user) and request.user not in booking.participants.all()):
        messages.error(request, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้"); return redirect('dashboard')
    return render(request, 'pages/booking_detail.html', {'booking': booking})

@login_required
def edit_profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save(); update_session_auth_hash(request, user)
                messages.success(request, 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว'); return redirect('edit_profile')
            else:
                profile_form = ProfileForm(instance=profile)
        else:
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                profile_form.save(); messages.success(request, 'อัปเดตโปรไฟล์เรียบร้อยแล้ว'); return redirect('edit_profile')
            else:
                password_form = CustomPasswordChangeForm(request.user)
    else:
        profile_form = ProfileForm(instance=profile)
        password_form = CustomPasswordChangeForm(request.user)
    return render(request, 'pages/edit_profile.html', {'profile_form': profile_form, 'password_form': password_form})

# --- Admin Dashboard View ---
@login_required
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_bookings = Booking.objects.filter(start_time__gte=thirty_days_ago, status='APPROVED')
    room_usage = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent_bookings))).order_by('-count')
    dept_usage = Profile.objects.filter(user__booking__in=recent_bookings).exclude(department__exact='').values('department').annotate(count=Count('user__booking')).order_by('-count')
    context = {
        'pending_count': Booking.objects.filter(status='PENDING').count(),
        'today_bookings_count': Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count(),
        'total_users_count': User.objects.count(), 'total_rooms_count': Room.objects.count(),
        'login_history': LoginHistory.objects.all()[:7],
        'room_usage_labels': json.dumps([r.name for r in room_usage]), 'room_usage_data': json.dumps([r.count for r in room_usage]),
        'dept_usage_labels': json.dumps([d['department'] for d in dept_usage]),
        'dept_usage_data': json.dumps([d['count'] for d in dept_usage]),
    }
    return render(request, 'pages/admin_dashboard.html', context)

# --- API Views ---
@login_required
def bookings_api(request):
    start, end, room_id = request.GET.get('start'), request.GET.get('end'), request.GET.get('room_id')
    bookings = Booking.objects.filter(start_time__gte=start, end_time__lte=end)
    if room_id: bookings = bookings.filter(room_id=room_id)
    events = []
    for booking in bookings:
        color_map = {'APPROVED': '#198754', 'PENDING': '#ffc107', 'REJECTED': '#dc3545', 'CANCELLED': '#fd7e14'}
        color = color_map.get(booking.status, '#6c757d')
        event_title = f"[{booking.get_status_display()}] {booking.title}\n({booking.booked_by.username})"
        events.append({
            'id': booking.id, 'title': event_title, 'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(), 'color': color, 'borderColor': color,
            'extendedProps': {'room_id': booking.room.id, 'room_name': booking.room.name}
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
        if conflicts.exists(): return JsonResponse({'status': 'error', 'message': 'ช่วงเวลาที่เลือกไม่ว่าง'}, status=400)
        booking.start_time, booking.end_time = new_start, new_end; booking.save()
        admin_emails = get_admin_emails()
        send_booking_notification(booking, 'emails/booking_changed_alert.txt', f"[เปลี่ยนเวลา] {booking.title}", admin_emails)
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# --- Booking Action Views ---
@login_required
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            booking = form.save(commit=False); booking.booked_by = request.user; booking.save()
            form.save_m2m()
            messages.success(request, f"การจอง '{booking.title}' ถูกสร้างเรียบร้อยแล้ว รอการอนุมัติ")
            admin_emails = get_admin_emails()
            send_booking_notification(booking, 'emails/new_booking_alert.txt', f"[จองห้องใหม่] {booking.title}", admin_emails)
        else:
            for field, error_list in form.errors.items():
                for error in error_list: messages.error(request, f"{form.fields.get(field).label if form.fields.get(field) else field}: {error}")
    return redirect('room_calendar', room_id=room.id)

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขการจองนี้"); return redirect('dashboard')
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            updated_booking = form.save()
            messages.success(request, "การจองถูกแก้ไขเรียบร้อยแล้ว")
            admin_emails = get_admin_emails()
            send_booking_notification(updated_booking, 'emails/booking_changed_alert.txt', f"[แก้ไขการจอง] {updated_booking.title}", admin_emails)
            return redirect('history')
    else: form = BookingForm(instance=booking)
    return render(request, 'pages/edit_booking.html', {'form': form, 'booking': booking})

@login_required
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์ยกเลิกการจองนี้"); return redirect('dashboard')
    if request.method == 'POST':
        booking.status = 'CANCELLED'; booking.save()
        messages.success(request, "การจองได้ถูกยกเลิกเรียบร้อยแล้ว")
        admin_emails = get_admin_emails()
        send_booking_notification(booking, 'emails/booking_cancelled_alert.txt', f"[ยกเลิกการจอง] {booking.title}", admin_emails)
        return redirect('room_calendar', room_id=booking.room.id)
    return redirect('dashboard')

# --- Approver & Admin Views ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending_bookings = Booking.objects.filter(status='PENDING').select_related('room', 'booked_by', 'booked_by__profile')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending_bookings})

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id); booking.status = 'APPROVED'; booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    if booking.booked_by.email:
        send_booking_notification(booking, 'emails/booking_status_update.txt', f"สถานะการจอง: '{booking.title}' ได้รับการอนุมัติแล้ว", [booking.booked_by.email])
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id); booking.status = 'REJECTED'; booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    if booking.booked_by.email:
        send_booking_notification(booking, 'emails/booking_status_update.txt', f"สถานะการจอง: '{booking.title}' ถูกปฏิเสธ", [booking.booked_by.email])
    return redirect('approvals')

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
            group = Group.objects.get(pk=group_id); user_to_edit.groups.add(group)
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

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    period = request.GET.get('period', 'monthly'); department_filter = request.GET.get('department', '')
    today = timezone.now().date()
    if period == 'daily': start_date, title = today, 'รายวัน'
    elif period == 'weekly': start_date, title = today - timedelta(days=7), 'รายสัปดาห์ (7 วันล่าสุด)'
    else: start_date, title = today - timedelta(days=30), 'รายเดือน (30 วันล่าสุด)'
    
    recent_bookings = Booking.objects.filter(start_time__date__gte=start_date, status='APPROVED')
    if department_filter:
        recent_bookings = recent_bookings.filter(booked_by__profile__department=department_filter)

    room_usage_stats = Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__in=recent_bookings))).order_by('-booking_count')
    all_departments = Profile.objects.exclude(department__exact='').values_list('department', flat=True).distinct().order_by('department')
    context = {
        'room_usage_stats': room_usage_stats, 'report_title': title, 'current_period': period,
        'all_departments': all_departments, 'current_department': department_filter,
    }
    return render(request, 'pages/reports.html', context)

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    period = request.GET.get('period', 'monthly'); department_filter = request.GET.get('department', '')
    today = timezone.now().date()
    if period == 'daily': start_date = today
    elif period == 'weekly': start_date = today - timedelta(days=7)
    else: start_date = today - timedelta(days=30)
    
    recent_bookings = Booking.objects.filter(start_time__date__gte=start_date, status='APPROVED')
    if department_filter: recent_bookings = recent_bookings.filter(booked_by__profile__department=department_filter)
    
    room_stats = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent_bookings))).order_by('-count')
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="report_{period}_{department_filter or "all"}.xlsx"'
    workbook = Workbook()
    ws = workbook.active; ws.title = "Room Usage"; ws.append(['ชื่อห้องประชุม', 'จำนวนครั้งที่ใช้งาน'])
    for room in room_stats: ws.append([room.name, room.count])
    workbook.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    period = request.GET.get('period', 'monthly'); department_filter = request.GET.get('department', '')
    today = timezone.now().date()
    if period == 'daily': start_date, title = today, 'รายงานสรุปรายวัน'
    elif period == 'weekly': start_date, title = today - timedelta(days=7), 'รายสัปดาห์'
    else: start_date, title = today - timedelta(days=30), 'รายเดือน'

    recent_bookings = Booking.objects.filter(start_time__date__gte=start_date, status='APPROVED')
    if department_filter:
        recent_bookings = recent_bookings.filter(booked_by__profile__department=department_filter)
        title += f" (แผนก: {department_filter})"

    room_usage_stats = Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__in=recent_bookings))).order_by('-booking_count')
    context = {'room_usage_stats': room_usage_stats, 'report_title': title, 'today_date': today}
    template = get_template('reports/report_pdf.html')
    html_string = template.render(context)
    html = HTML(string=html_string); pdf_file = html.write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{period}_{department_filter or "all"}.pdf"'
    return response