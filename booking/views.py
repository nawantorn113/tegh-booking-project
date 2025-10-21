# booking/views.py

import json
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.models import User, Group
# --- ต้องติดตั้ง: pip install django-autocomplete-light ---
try:
    from dal_select2.views import Select2QuerySetView
    DAL_AVAILABLE = True
except ImportError:
    print("\n!!! WARNING: django-autocomplete-light (dal_select2) not installed. Autocomplete fields WILL NOT WORK. !!!\n")
    DAL_AVAILABLE = False
    class Select2QuerySetView: pass # Placeholder class
# --- -------------------------------------------- ---
from django.core.mail import send_mail
from django.template.loader import render_to_string, get_template
from django.conf import settings
# --- ต้องติดตั้ง: pip install openpyxl ---
try:
    from openpyxl import Workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    print("\n!!! WARNING: openpyxl not installed. Excel export WILL NOT WORK. !!!\n")
    OPENPYXL_AVAILABLE = False
# --- -------------------------------- ---
from django.utils import timezone
# --- ต้องติดตั้ง: pip install WeasyPrint ---
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    print("\n!!! WARNING: WeasyPrint not installed. PDF export WILL NOT WORK. !!!\n")
    WEASYPRINT_AVAILABLE = False
# --- ---------------------------------- ---
from collections import defaultdict
from .models import Room, Booking, Profile, LoginHistory # Ensure all models are imported
from .forms import BookingForm, ProfileForm, CustomPasswordChangeForm, RoomForm # Ensure all forms are imported
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.forms import AuthenticationForm

# --- Login/Logout History ---
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip_address = request.META.get('REMOTE_ADDR')
    LoginHistory.objects.create(user=user, action='LOGIN', ip_address=ip_address)

@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
        ip_address = request.META.get('REMOTE_ADDR')
        LoginHistory.objects.create(user=user, action='LOGOUT', ip_address=ip_address)

# --- Helper Functions (สำคัญสำหรับ Sidebar) ---
def is_admin(user): 
    return user.is_authenticated and user.groups.filter(name='Admin').exists()
def is_approver_or_admin(user): 
    return user.is_authenticated and user.groups.filter(name__in=['Approver', 'Admin']).exists()
# --- ------------------------------------ ---

def get_admin_emails(): return list(User.objects.filter(groups__name__in=['Admin', 'Approver'], is_active=True).exclude(email__exact='').values_list('email', flat=True))
def send_booking_notification(booking, template, subject, recipients=None):
    if recipients is None: recipients = get_admin_emails()
    if not recipients: print(f"Skipping email '{subject}': No recipients."); return
    if not isinstance(recipients, list): recipients = [recipients]
    context = {'booking': booking, 'settings': settings}
    try:
        message = render_to_string(template, context)
        # Simulate or send email based on settings
        if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
            print(f"Email '{subject}' sent to: {', '.join(recipients)}")
        else: print(f"--- Email Sim '{subject}' To: {', '.join(recipients)} ---\n{message}\n--- End Sim ---")
    except Exception as e: print(f"Error preparing/sending email '{subject}': {e}")

# --- Autocomplete ---
if DAL_AVAILABLE:
    class UserAutocomplete(Select2QuerySetView):
        def get_queryset(self):
            if not self.request.user.is_authenticated: return User.objects.none()
            qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
            if self.q: qs = qs.filter( Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q) | Q(email__icontains=self.q) )
            return qs[:15]
        def get_result_label(self, item): return f"{item.get_full_name() or item.username} ({item.email or 'No email'})"
else: # Placeholder if DAL not installed
    @login_required
    def UserAutocomplete(request): return JsonResponse({'error': 'Autocomplete unavailable.'}, status=501)

# --- Auth ---
def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST); print("Login POST received.")
        if form.is_valid():
            user = form.get_user(); print(f"Auth success: {user.username}"); login(request, user)
            if request.user.is_authenticated: print(f"Session login OK for {request.user.username}. Redirecting...")
            else: print(f"!!! LOGIN FAILED for {user.username} !!!")
            next_url = request.GET.get('next', 'dashboard'); messages.success(request, f'ยินดีต้อนรับ, {user.get_full_name() or user.username}!')
            return redirect(next_url)
        else: print("Auth failed:", form.errors.as_data()); messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
    else: form = AuthenticationForm(); print("Serving login page (GET).")
    return render(request, 'login.html', {'form': form})

@login_required
def logout_view(request):
    user_before = request.user; logout(request)
    user_logged_out.send(sender=user_before.__class__, request=request, user=user_before)
    messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว'); return redirect('login')

# --- Main Pages ---
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
        current = room.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').select_related('booked_by').first()
        room.status = 'ไม่ว่าง' if current else 'ว่าง'; room.current_booking_info = current
        room.next_booking_info = None if current else room.bookings.filter(start_time__gt=now, status='APPROVED').select_related('booked_by').order_by('start_time').first()
        room.equipment_list = [eq.strip() for eq in (room.equipment_in_room or "").splitlines() if eq.strip()]
        buildings[room.building or "(ไม่ได้ระบุอาคาร)"].append(room)
    summary = { 'total_rooms': Room.objects.count(), 'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(), 'pending_approvals': Booking.objects.filter(status='PENDING').count(), }
    context = {'buildings': dict(buildings), 'summary_cards': summary, 'current_sort': sort_by}
    return render(request, 'pages/dashboard.html', context)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id); form = BookingForm(initial={'room': room})
    # context_processors.py จะส่ง is_admin_user มาให้อัตโนมัติ
    context = {'room': room, 'form': form}
    return render(request, 'pages/room_calendar.html', context)

@login_required
def master_calendar_view(request):
    return render(request, 'pages/master_calendar.html')

@login_required
def history_view(request):
    bookings = Booking.objects.filter(booked_by=request.user).select_related('room').order_by('-start_time')
    date_f = request.GET.get('date'); room_f = request.GET.get('room'); status_f = request.GET.get('status')
    try:
        if date_f: bookings = bookings.filter(start_time__date=datetime.strptime(date_f, '%Y-%m-%d').date())
    except ValueError: messages.warning(request, "Invalid date format"); date_f = None
    if room_f: bookings = bookings.filter(room__id=room_f)
    if status_f: bookings = bookings.filter(status=status_f)
    context = { 'my_bookings': bookings, 'all_rooms': Room.objects.all().order_by('name'), 'status_choices': Booking.STATUS_CHOICES, 'current_date': date_f, 'current_room': room_f, 'current_status': status_f, }
    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('room', 'booked_by', 'booked_by__profile').prefetch_related('participants'), pk=booking_id)
    is_participant = request.user in booking.participants.all()
    if (booking.booked_by != request.user and not is_admin(request.user) and not is_participant):
        messages.error(request, "No access"); return redirect('dashboard')
    context = {'booking': booking} # is_admin จะถูกส่งจาก context_processor
    return render(request, 'pages/booking_detail.html', context)

@login_required
def edit_profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(request.user, request.POST)
            profile_form = ProfileForm(instance=profile) # Keep current profile data
            if password_form.is_valid():
                user = password_form.save(); update_session_auth_hash(request, user)
                messages.success(request, 'Password changed'); return redirect('edit_profile')
        else: # Profile update
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            password_form = CustomPasswordChangeForm(request.user) # Keep password form
            if profile_form.is_valid():
                profile_form.save()
                request.user.first_name = request.POST.get('first_name', request.user.first_name)
                request.user.last_name = request.POST.get('last_name', request.user.last_name)
                request.user.email = request.POST.get('email', request.user.email) # If email is editable
                request.user.save()
                messages.success(request, 'Profile updated'); return redirect('edit_profile')
    else: # GET request
        profile_form = ProfileForm(instance=profile, initial={'first_name': request.user.first_name, 'last_name': request.user.last_name, 'email': request.user.email,})
        password_form = CustomPasswordChangeForm(request.user)
    return render(request, 'pages/edit_profile.html', {'profile_form': profile_form, 'password_form': password_form})

# --- Admin ---
@login_required
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent = Booking.objects.filter(start_time__gte=thirty_days_ago, status='APPROVED')
    room_usage = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent))).order_by('-count')
    dept_usage = Profile.objects.filter(user__booking__in=recent).exclude(department__exact='').values('department').annotate(count=Count('user__booking', filter=Q(user__booking__in=recent))).order_by('-count')
    context = {
        'pending_count': Booking.objects.filter(status='PENDING').count(), 'today_bookings_count': Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count(),
        'total_users_count': User.objects.count(), 'total_rooms_count': Room.objects.count(),
        'login_history': LoginHistory.objects.select_related('user').order_by('-timestamp')[:7],
        'room_usage_labels': json.dumps([r.name for r in room_usage]), 'room_usage_data': json.dumps([r.count for r in room_usage]),
        'dept_usage_labels': json.dumps([d['department'] for d in dept_usage if d.get('department')]), 'dept_usage_data': json.dumps([d['count'] for d in dept_usage if d.get('department')]),
    }
    return render(request, 'pages/admin_dashboard.html', context)

# --- APIs ---
@login_required
def rooms_api(request):
    rooms = Room.objects.all().order_by('building', 'name')
    resources = [{'id': r.id, 'title': r.name, 'building': r.building or ""} for r in rooms]
    return JsonResponse(resources, safe=False)

@login_required
def bookings_api(request):
    start_str = request.GET.get('start'); end_str = request.GET.get('end'); room_id = request.GET.get('room_id')
    try: start_dt = timezone.make_aware(datetime.fromisoformat(start_str.replace('Z', '+00:00'))) if start_str else None; end_dt = timezone.make_aware(datetime.fromisoformat(end_str.replace('Z', '+00:00'))) if end_str else None
    except: return JsonResponse({'error': 'Invalid date'}, status=400)
    if not start_dt or not end_dt: return JsonResponse({'error': 'Start/end required'}, status=400)
    bookings = Booking.objects.filter(start_time__lt=end_dt, end_time__gt=start_dt).select_related('room', 'booked_by')
    if room_id: bookings = bookings.filter(room_id=room_id)
    events = [{'id': b.id, 'title': b.title, 'start': b.start_time.isoformat(), 'end': b.end_time.isoformat(), 'resourceId': b.room.id,
                'extendedProps': { 
                    'room_id': b.room.id, 
                    'room_name': b.room.name, 
                    'booked_by_username': b.booked_by.username, 
                    'status': b.status,
                    'user_id': b.booked_by.id  # <-- สำคัญมากสำหรับ eventClick
                 }}
                for b in bookings]
    return JsonResponse(events, safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        b_id = data.get('booking_id'); start_s = data.get('start_time'); end_s = data.get('end_time')
        if not all([b_id, start_s, end_s]): return JsonResponse({'status': 'error', 'message': 'Missing data.'}, status=400)
        booking = get_object_or_404(Booking, pk=b_id)
        if booking.booked_by != request.user and not is_admin(request.user): return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        try: new_s = timezone.make_aware(datetime.fromisoformat(start_s.replace('Z', '+00:00'))); new_e = timezone.make_aware(datetime.fromisoformat(end_s.replace('Z', '+00:00')))
        except ValueError: return JsonResponse({'status': 'error', 'message': 'Invalid date.'}, status=400)
        if new_e <= new_s: return JsonResponse({'status': 'error', 'message': 'End <= Start.'}, status=400)
        conflicts = Booking.objects.filter(room=booking.room, start_time__lt=new_e, end_time__gt=new_s).exclude(pk=booking.id).exclude(status__in=['REJECTED', 'CANCELLED'])
        if conflicts.exists(): return JsonResponse({'status': 'error', 'message': 'ช่วงเวลาทับซ้อน'}, status=400)
        booking.start_time, booking.end_time = new_s, new_e
        if booking.participant_count >= 15 and booking.status != 'PENDING':
             booking.status = 'PENDING'; messages.info(request, "การเปลี่ยนแปลงเวลาทำให้ต้องรอการอนุมัติใหม่")
        booking.save()
        return JsonResponse({'status': 'success', 'message': 'Booking time updated.'})
    except json.JSONDecodeError: return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    except Booking.DoesNotExist: return JsonResponse({'status': 'error', 'message': 'Booking not found.'}, status=404)
    except Exception as e: print(f"Error update_booking_time_api: {e}"); return JsonResponse({'status': 'error', 'message': 'Server error.'}, status=500)

@login_required
@require_http_methods(["POST"]) # อนุญาตเฉพาะ POST
def delete_booking_api(request, booking_id):
    """
    API View สำหรับลบ (ยกเลิก) การจอง (คืนค่า JSON)
    """
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        if booking.booked_by != request.user and not is_admin(request.user):
            return JsonResponse({'success': False, 'error': 'ไม่มีสิทธิ์ยกเลิก'}, status=403)
        if booking.status in ['CANCELLED', 'REJECTED']:
            return JsonResponse({'success': False, 'error': 'การจองนี้ถูกยกเลิก/ปฏิเสธไปแล้ว'})
        booking.status = 'CANCELLED'
        booking.save()
        return JsonResponse({'success': True, 'message': 'ยกเลิกการจองเรียบร้อย'})
    except Booking.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'ไม่พบการจองนี้'}, status=404)
    except Exception as e:
        print(f"Error delete_booking_api: {e}")
        return JsonResponse({'success': False, 'error': 'เกิดข้อผิดพลาดบนเซิร์ฟเวอร์'}, status=500)


# --- Booking Actions (with participant count approval logic) ---
@login_required
@require_POST
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    temp_booking = Booking(room=room) # Pass room for validation
    form = BookingForm(request.POST, request.FILES, instance=temp_booking)
    if form.is_valid():
        booking = form.save(commit=False); booking.booked_by = request.user
        participant_count = form.cleaned_data.get('participant_count', 1)
        if participant_count >= 15: # <-- เงื่อนไขการอนุมัติ
            booking.status = 'PENDING'; messages.success(request, f"จอง '{booking.title}' ({room.name}) เรียบร้อย **รออนุมัติ** (ผู้เข้าร่วม {participant_count} คน)")
            # send_booking_notification(booking, 'emails/new_booking_alert.txt', f"[จองใหม่-รออนุมัติ] {booking.title}")
        else:
            booking.status = 'APPROVED'; messages.success(request, f"จอง '{booking.title}' ({room.name}) **อนุมัติอัตโนมัติ** เรียบร้อยแล้ว")
        booking.save(); form.save_m2m() 
        return redirect('room_calendar', room_id=room.id)
    else: # Form invalid
        error_str = "; ".join([f"{f}: {', '.join(e)}" for f, e in form.errors.items()])
        messages.error(request, f"ไม่สามารถจองได้: {error_str}")
        print("Booking form errors:", form.errors.as_json())
        return redirect('room_calendar', room_id=room.id) 


@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user): messages.error(request, "ไม่มีสิทธิ์แก้ไข"); return redirect('history')
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            updated = form.save(commit=False)
            new_count = form.cleaned_data.get('participant_count', 1)
            changed = form.has_changed() and any(f in form.changed_data for f in ['start_time', 'end_time', 'participant_count'])
            if new_count >= 15 and changed and updated.status not in ['PENDING', 'REJECTED', 'CANCELLED']: 
                 updated.status = 'PENDING'; messages.info(request, "การแก้ไขต้องรอการอนุมัติใหม่ (จำนวนผู้เข้าร่วม)")
            updated.save(); form.save_m2m()
            messages.success(request, "แก้ไขการจองเรียบร้อย"); return redirect('history')
    else: # GET
        form = BookingForm(instance=booking)
    return render(request, 'pages/edit_booking.html', {'form': form, 'booking': booking})


@login_required
@require_POST
def delete_booking_view(request, booking_id):
    # (View นี้สำหรับปุ่มลบในหน้า History - คืนค่า Redirect)
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user): messages.error(request, "ไม่มีสิทธิ์ยกเลิก"); return redirect('history')
    if booking.status in ['CANCELLED', 'REJECTED']: messages.warning(request, "ถูกยกเลิก/ปฏิเสธไปแล้ว"); return redirect('history')
    original = booking.status; booking.status = 'CANCELLED'; booking.save()
    messages.success(request, "ยกเลิกการจองเรียบร้อย")
    return redirect('history')

# --- Approvals ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending = Booking.objects.filter(status='PENDING').select_related('room', 'booked_by', 'booked_by__profile').order_by('start_time')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending})

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, status='PENDING') 
    booking.status = 'APPROVED'; booking.save()
    messages.success(request, f"อนุมัติ '{booking.title}' เรียบร้อย")
    # if booking.booked_by.email: send_booking_notification(booking, 'emails/booking_status_update.txt', f"การจอง '{booking.title}' อนุมัติแล้ว", [booking.booked_by.email])
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, status='PENDING')
    booking.status = 'REJECTED'; booking.save()
    messages.warning(request, f"ปฏิเสธ '{booking.title}'")
    # if booking.booked_by.email: send_booking_notification(booking, 'emails/booking_status_update.txt', f"การจอง '{booking.title}' ถูกปฏิเสธ", [booking.booked_by.email])
    return redirect('approvals')

# --- Management ---
@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    users = User.objects.all().order_by('username').prefetch_related('groups', 'profile')
    return render(request, 'pages/user_management.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    user_edit = get_object_or_404(User, pk=user_id); all_groups = Group.objects.all()
    if request.method == 'POST':
        group_ids = request.POST.getlist('groups'); valid_groups = Group.objects.filter(pk__in=group_ids)
        user_edit.groups.set(valid_groups); user_edit.is_staff = user_edit.groups.filter(name='Admin').exists(); user_edit.save()
        messages.success(request, f"อัปเดตสิทธิ์ '{user_edit.username}' เรียบร้อย")
        return redirect('user_management')
    context = {'user_to_edit': user_edit, 'all_groups': all_groups}
    return render(request, 'pages/edit_user_roles.html', context)

@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    rooms = Room.objects.all().order_by('building', 'name')
    return render(request, 'pages/rooms.html', {'rooms': rooms})

@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES) 
        if form.is_valid(): form.save(); messages.success(request, "เพิ่มห้องใหม่เรียบร้อย"); return redirect('rooms')
    else: form = RoomForm()
    return render(request, 'pages/room_form.html', {'form': form, 'title': 'เพิ่มห้องประชุมใหม่'})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid(): form.save(); messages.success(request, "แก้ไขข้อมูลห้องเรียบร้อย"); return redirect('rooms')
    else: form = RoomForm(instance=room)
    return render(request, 'pages/room_form.html', {'form': form, 'title': f'แก้ไข: {room.name}'})

@login_required
@user_passes_test(is_admin)
@require_POST
def delete_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id); name = room.name
    try: room.delete(); messages.success(request, f"ลบห้อง '{name}' เรียบร้อย")
    except Exception as e: messages.error(request, f"ไม่สามารถลบห้อง '{name}': {e}")
    return redirect('rooms')

# --- Reports ---
@login_required
@user_passes_test(is_admin)
def reports_view(request):
    period = request.GET.get('period', 'monthly'); dept = request.GET.get('department', ''); today = timezone.now().date()
    try:
        if period == 'daily': start, title = today, f'รายวัน ({today:%d %b %Y})'
        elif period == 'weekly': start = today - timedelta(days=6); title = f'รายสัปดาห์ ({start:%d %b} - {today:%d %b %Y})'
        else: start = today - timedelta(days=29); title = f'รายเดือน ({start:%d %b} - {today:%d %b %Y})'
    except: start = today - timedelta(days=29); title = 'รายเดือน (ผิดพลาด)'; period = 'monthly'
    recent = Booking.objects.filter(start_time__date__gte=start, start_time__date__lte=today, status='APPROVED')
    if dept: recent = recent.filter(booked_by__profile__department=dept)
    stats = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent))).filter(count__gt=0).order_by('-count')
    depts = Profile.objects.exclude(department__exact='').values_list('department', flat=True).distinct().order_by('department')
    context = { 'room_usage_stats': stats, 'report_title': title, 'current_period': period, 'all_departments': depts, 'current_department': dept, }
    return render(request, 'pages/reports.html', context)

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    if not OPENPYXL_AVAILABLE: messages.error(request, "ไม่ได้ติดตั้ง openpyxl"); return redirect('reports')
    period = request.GET.get('period', 'monthly'); dept = request.GET.get('department', '')
    today = timezone.now().date(); start = today - timedelta(days={'daily':0, 'weekly':6}.get(period, 29))
    recent = Booking.objects.filter(start_time__date__gte=start, start_time__date__lte=today, status='APPROVED')
    if dept: recent = recent.filter(booked_by__profile__department=dept)
    stats = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent))).filter(count__gt=0).order_by('-count')
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    fname = f'report_{period}_{dept or "all"}_{today:%Y%m%d}.xlsx'; response['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb = Workbook(); ws = wb.active; ws.title = "Room Usage"; ws.append(['ชื่อห้อง', 'จำนวนครั้ง'])
    for room in stats: ws.append([room.name, room.count])
    ws.column_dimensions['A'].width = 30; ws.column_dimensions['B'].width = 15; wb.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    if not WEASYPRINT_AVAILABLE: messages.error(request, "ไม่ได้ติดตั้ง WeasyPrint"); return redirect('reports')
    period = request.GET.get('period', 'monthly'); dept = request.GET.get('department', '')
    today = timezone.now().date()
    if period == 'daily': start, title = today, f'รายวัน ({today:%d %b %Y})'
    elif period == 'weekly': start = today - timedelta(days=6); title = f'รายสัปดาห์ ({start:%d %b} - {today:%d %b %Y})'
    else: start = today - timedelta(days=29); title = f'รายเดือน ({start:%d %b} - {today:%d %b %Y})'
    recent = Booking.objects.filter(start_time__date__gte=start, start_time__date__lte=today, status='APPROVED')
    if dept: recent = recent.filter(booked_by__profile__department=dept); title += f" (แผนก: {dept})"
    stats = Room.objects.annotate(count=Count('bookings', filter=Q(bookings__in=recent))).filter(count__gt=0).order_by('-count')
    context = { 'room_usage_stats': stats, 'report_title': title, 'today_date': today, 'base_url': request.build_absolute_uri('/') }
    template_path = 'reports/report_pdf.html'
    try: template = get_template(template_path); html_string = template.render(context)
    except Exception as e: messages.error(request, f"Error loading PDF template '{template_path}': {e}"); return redirect('reports')
    try:
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/')); pdf = html.write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        fname = f'report_{period}_{dept or "all"}_{today:%Y%m%d}.pdf'; response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response
    except Exception as e: messages.error(request, f"Error generating PDF: {e}"); return redirect('reports')