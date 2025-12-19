import json
import re
import csv
import uuid
from datetime import datetime, timedelta, time
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from dateutil import parser 

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.template.loader import get_template, render_to_string
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from dal_select2.views import Select2QuerySetView
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt

try:
    from weasyprint import HTML, CSS
except ImportError:
    HTML = None
    CSS = None

try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.models import TextSendMessage, MessageEvent, TextMessage
    from linebot.exceptions import InvalidSignatureError
except ImportError:
    LineBotApi = None
    WebhookHandler = None

from .models import Room, Booking, AuditLog, OutlookToken, UserProfile, Equipment
from .forms import BookingForm, RoomForm, CustomUserCreationForm, EquipmentForm
from .outlook_client import OutlookClient

line_bot_api = None
handler = None
if hasattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN') and hasattr(settings, 'LINE_CHANNEL_SECRET'):
    try:
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
    except:
        pass

# ----------------------------------------------------------------------
# A. HELPER FUNCTIONS
# ----------------------------------------------------------------------

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff or user.groups.filter(name='Admin').exists())

def is_approver_or_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff or user.groups.filter(name__in=['Approver', 'Admin']).exists())

def get_admin_emails():
    return list(User.objects.filter(Q(groups__name='Admin') | Q(is_superuser=True) | Q(is_staff=True), is_active=True).distinct().exclude(email__exact='').values_list('email', flat=True))

def log_action(request, action_key, target_obj=None, detail_text=""):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
        full_details = detail_text
        if target_obj:
            full_details = f"{detail_text} [Target: {target_obj}]"
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action_key,
            details=full_details,
            ip_address=ip
        )
    except Exception as e:
        print(f"Log Error: {e}")

def get_outlook_client(request):
    redirect_uri = request.build_absolute_uri(reverse('outlook_callback'))
    return OutlookClient(redirect_uri)

def get_valid_token(user, request):
    try:
        token_obj = OutlookToken.objects.get(user=user)
        if token_obj.expires_at <= timezone.now() + timedelta(seconds=60):
            client = get_outlook_client(request)
            try:
                new_tokens = client.refresh_token(token_obj.refresh_token)
                token_obj.access_token = new_tokens['access_token']
                if 'refresh_token' in new_tokens:
                    token_obj.refresh_token = new_tokens['refresh_token']
                token_obj.expires_at = timezone.now() + timedelta(seconds=new_tokens['expires_in'])
                token_obj.save()
            except:
                return None
        return token_obj.access_token
    except OutlookToken.DoesNotExist:
        return None

def get_base_context(request):
    current_url_name = request.resolver_match.url_name if request.resolver_match else ''
    is_admin_user = is_admin(request.user)

    menu_structure = [
        {'label': 'หน้าหลัก', 'url_name': 'dashboard', 'icon': 'bi-house-fill', 'show': True},
        {'label': 'ปฏิทินรวม', 'url_name': 'master_calendar', 'icon': 'bi-calendar3-range', 'show': True},
        {'label': 'ประวัติการจอง', 'url_name': 'history', 'icon': 'bi-clock-history', 'show': True},
        {'label': 'รออนุมัติ', 'url_name': 'approvals', 'icon': 'bi-check2-circle', 'show': is_approver_or_admin(request.user)},
    ]

    admin_menu_structure = [
        {'label': 'จัดการห้องประชุม', 'url_name': 'rooms', 'icon': 'bi-door-open-fill', 'show': is_admin_user},
        {'label': 'จัดการอุปกรณ์', 'url_name': 'equipments', 'icon': 'bi-tools', 'show': is_admin_user}, 
        {'label': 'จัดการผู้ใช้งาน', 'url_name': 'user_management', 'icon': 'bi-people-fill', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'url_name': 'reports', 'icon': 'bi-bar-chart-fill', 'show': is_admin_user},
        {'label': 'ประวัติการใช้งาน', 'url_name': 'audit_log', 'icon': 'bi-clipboard-data-fill', 'show': is_admin_user},
    ]

    menu_items = []
    for item in menu_structure:
        if item['show']:
            item['active'] = (item['url_name'] == current_url_name)
            menu_items.append(item)

    admin_menu_items = []
    for item in admin_menu_structure:
        if item['show']:
            item['active'] = (item['url_name'] == current_url_name)
            admin_menu_items.append(item)

    pending_count = 0
    pending_notifications = []
    recent_cancellations = []

    if request.user.is_authenticated:
        if is_approver_or_admin(request.user):
            if is_admin(request.user):
                qs = Booking.objects.filter(status='PENDING').select_related('room', 'user').order_by('-created_at')
            else:
                qs = Booking.objects.filter(room__approver=request.user, status='PENDING').select_related('room', 'user').order_by('-created_at')
            
            pending_items_count = qs.count()
            pending_notifications = qs[:10]

            cancellations_qs = Booking.objects.filter(
                status='CANCELLED',
                updated_at__gte=timezone.now() - timedelta(days=1),
                is_user_seen=False
            ).select_related('room', 'user').order_by('-updated_at')

            cancel_items_count = cancellations_qs.count()
            recent_cancellations = cancellations_qs[:10]
            
            pending_count = pending_items_count + cancel_items_count
        
        else:
            qs = Booking.objects.filter(
                user=request.user,
                is_user_seen=False
            ).exclude(status='PENDING').select_related('room').order_by('-updated_at')
            
            pending_count = qs.count()
            pending_notifications = qs

    return {
        'menu_items': menu_items,
        'admin_menu_items': admin_menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,
        'pending_notifications': pending_notifications,
        'recent_cancellations': recent_cancellations,
    }

@login_required
@require_POST
def mark_notification_read(request, booking_id):
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        if request.user == booking.user or is_admin(request.user) or is_approver_or_admin(request.user):
            booking.is_user_seen = True
            booking.save()
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def send_booking_notification(booking, template_name, subject_prefix):
    equip_text = "-"
    if hasattr(booking, 'equipments') and booking.equipments.exists():
        equip_names = [eq.name for eq in booking.equipments.all()]
        equip_text = ", ".join(equip_names)

    note_text = booking.additional_requests if booking.additional_requests else "-"
    start_str = booking.start_time.strftime('%d/%m/%Y %H:%M')
    end_str = booking.end_time.strftime('%H:%M')
    user_name = booking.user.get_full_name() or booking.user.username

    layout_line = ""
    if booking.room.name == 'ห้องประชุมใหญ่':
        layout_display = booking.get_room_layout_display()
        if booking.room_layout == 'other' and booking.room_layout_attachment:
            layout_display += f" (ไฟล์แนบ: {booking.room_layout_attachment.url})"
        layout_line = f"รูปแบบ: {layout_display}\n"

    msg = (f"{subject_prefix}\n"
           f"ผู้จอง: {user_name}\n"
           f"ห้อง: {booking.room.name}\n"
           f"เรื่อง: {booking.title}\n"
           f"เวลา: {start_str} - {end_str}\n"
           f"จำนวนคน: {booking.participant_count} คน\n"
           f"{layout_line}"
           f"อุปกรณ์ที่ขอ: {equip_text}\n"
           f"เพิ่มเติม: {note_text}\n"
           f"\n"
           f"สถานะ: {booking.get_status_display()}")

    if line_bot_api:
        line_targets = set()
        try:
            if hasattr(booking.user, 'profile') and booking.user.profile.line_user_id:
                line_targets.add(booking.user.profile.line_user_id)
        except: pass
        
        if booking.room.approver:
            try:
                if hasattr(booking.room.approver, 'profile') and booking.room.approver.profile.line_user_id:
                    line_targets.add(booking.room.approver.profile.line_user_id)
            except: pass

        admins = User.objects.filter(is_superuser=True)
        for admin in admins:
            try:
                if hasattr(admin, 'profile') and admin.profile.line_user_id:
                    line_targets.add(admin.profile.line_user_id)
            except: pass

        for uid in line_targets:
            if uid:
                try: line_bot_api.push_message(uid, TextSendMessage(text=msg))
                except: pass

    admin_emails = get_admin_emails()
    if admin_emails:
        try:
            send_mail(
                subject=f"[{subject_prefix}] จองห้อง: {booking.title}",
                message=msg,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True,
            )
        except: pass

# ----------------------------------------------------------------------
# B. AUTH VIEWS
# ----------------------------------------------------------------------

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.filter(is_active=True).order_by('first_name', 'username')
        if self.q:
            q_filter = (
                Q(username__icontains=self.q) | 
                Q(first_name__icontains=self.q) | 
                Q(last_name__icontains=self.q)
            )
            qs = qs.filter(q_filter)
        return qs[:15]

class EquipmentAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Equipment.objects.none()
        qs = Equipment.objects.all().order_by('name')
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            log_action(request, 'LOGIN', None, "เข้าสู่ระบบสำเร็จ")
            return redirect('dashboard')
        else:
            messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = AuthenticationForm()
    return render(request, 'login_card.html', {'form': form})

@login_required
def logout_view(request):
    log_action(request, 'LOGIN', None, "ออกจากระบบ")
    logout(request)
    return redirect('login')

@login_required
def outlook_login_view(request):
    client = get_outlook_client(request)
    return redirect(client.get_auth_url())

@login_required
def outlook_callback_view(request):
    code = request.GET.get('code')
    if code:
        client = get_outlook_client(request)
        try:
            tokens = client.get_token_from_code(code)
            exp = timezone.now() + timedelta(seconds=tokens.get('expires_in', 3600) - 60)
            OutlookToken.objects.update_or_create(
                user=request.user,
                defaults={'access_token': tokens['access_token'], 'refresh_token': tokens.get('refresh_token'), 'expires_at': exp}
            )
            log_action(request, 'LOGIN', None, "เชื่อมต่อ Outlook สำเร็จ")
            messages.success(request, "เชื่อมต่อ Outlook สำเร็จ!")
        except Exception as e:
            messages.error(request, f"Error: {e}")
    return redirect('dashboard')

# ----------------------------------------------------------------------
# C. MAIN VIEWS
# ----------------------------------------------------------------------

def public_calendar_view(request):
    ctx = get_base_context(request)
    ctx.update({'all_rooms': Room.objects.all(), 'is_public_view': True})
    return render(request, 'pages/master_calendar.html', ctx)

@login_required 
def smart_search_view(request):
    query = request.GET.get('q', '').strip()
    rooms = Room.objects.all()
    if query:
        match = re.search(r'(\d+)', query)
        capacity = int(match.group(1)) if match else None
        kw = re.sub(r'\d+\s*(คน|ท่าน)?', '', query).strip()
        if capacity: rooms = rooms.filter(capacity__gte=capacity)
        if kw: rooms = rooms.filter(Q(name__icontains=kw) | Q(building__icontains=kw))
    ctx = get_base_context(request)
    ctx.update({'query': query, 'available_rooms': rooms, 'search_count': rooms.count()})
    return render(request, 'pages/search_results.html', ctx)

@login_required
def dashboard_view(request):
    now = timezone.now()
    sort_by = request.GET.get('sort', 'floor')
    all_rooms = Room.objects.all()
    active_bookings = Booking.objects.filter(start_time__lte=now, end_time__gt=now, status__in=['APPROVED', 'PENDING']).select_related('user', 'room')
    room_booking_map = {b.room_id: b for b in active_bookings}
    rooms_processed = []
    buildings = defaultdict(list)

    for r in all_rooms:
        current_booking = room_booking_map.get(r.id)
        r.current_booking_info = current_booking
        r.is_maintenance = r.is_currently_under_maintenance
        if r.is_maintenance:
            r.status, r.status_class = 'ปิดปรับปรุง', 'bg-secondary text-white'
        elif current_booking:
            if current_booking.status == 'PENDING':
                r.status, r.status_class = 'รออนุมัติ', 'bg-warning text-dark'
            else:
                r.status, r.status_class = 'ไม่ว่าง', 'bg-danger text-white'
        else:
            r.status, r.status_class = 'ว่าง', 'bg-success text-white'
        rooms_processed.append(r)

    if sort_by == 'status':
        status_priority = {'ว่าง': 0, 'รออนุมัติ': 1, 'ไม่ว่าง': 2, 'ปิดปรับปรุง': 3}
        rooms_processed.sort(key=lambda x: status_priority.get(x.status, 99))
    elif sort_by == 'capacity':
        rooms_processed.sort(key=lambda x: x.capacity, reverse=True)
    elif sort_by == 'name':
        rooms_processed.sort(key=lambda x: x.name)
    else:
        rooms_processed.sort(key=lambda x: (x.building or '', str(x.floor or ''), x.name))

    for r in rooms_processed:
        buildings[r.building or "อาคารทั่วไป"].append(r)

    summary = {
        'total_rooms': all_rooms.count(),
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': Booking.objects.filter(status='PENDING').count(),
        'total_users_count': User.objects.count()
    }
    
    ctx = get_base_context(request)
    ctx.update({'buildings': dict(buildings), 'summary_cards': summary, 'current_sort': sort_by})
    return render(request, 'pages/dashboard.html', ctx)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            # --- ตรวจสอบเวลาจอง ---
            booking_start = form.cleaned_data.get('start_time')
            now = timezone.now()

            if booking_start < now:
                messages.error(request, "ไม่สามารถจองย้อนหลังได้ กรุณาเลือกเวลาใหม่")
                return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})

            if booking_start < now + timedelta(minutes=30):
                messages.error(request, "กรุณาจองล่วงหน้าอย่างน้อย 30 นาที เพื่อเตรียมห้องและอุปกรณ์")
                return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})
            
            recurrence = form.cleaned_data.get('recurrence')
            recurrence_end_date = form.cleaned_data.get('recurrence_end_date')
            has_equipments = bool(form.cleaned_data.get('equipments'))

            base_booking = form.save(commit=False)
            base_booking.room = room
            base_booking.user = request.user
            
            duration = base_booking.end_time - base_booking.start_time
            current_start = base_booking.start_time
            
            bookings_to_create = []
            conflict_dates = []
            
            loop_limit = recurrence_end_date if (recurrence != 'NONE' and recurrence_end_date) else current_start.date()

            while current_start.date() <= loop_limit:
                current_end = current_start + duration
                
                # --- Buffer Time 30 นาที ---
                buffer_time = timedelta(minutes=30)
                is_overlap = Booking.objects.filter(
                    room=room, 
                    start_time__lt=current_end + buffer_time, 
                    end_time__gt=current_start - buffer_time,
                    status__in=['APPROVED', 'PENDING']
                ).exists()
                
                if is_overlap:
                    conflict_dates.append(f"{current_start.strftime('%d/%m/%Y %H:%M')} (ติดระยะเวลาพักห้อง 30 นาที)")
                bookings_to_create.append({'start': current_start, 'end': current_end})
                
                if recurrence == 'WEEKLY': current_start += timedelta(weeks=1)
                elif recurrence == 'MONTHLY': current_start += relativedelta(months=1)
                else: break

            if conflict_dates:
                messages.error(request, f"ไม่สามารถจองได้เนื่องจากเวลาทับซ้อนหรือติดระยะพักห้อง: {', '.join(conflict_dates)}")
            else:
                count = 0
                for info in bookings_to_create:
                    new_b = Booking(
                        title=base_booking.title, room=room, user=request.user,
                        start_time=info['start'], end_time=info['end'],
                        participant_count=base_booking.participant_count,
                        description=base_booking.description,
                        additional_requests=base_booking.additional_requests,
                        additional_notes=base_booking.additional_notes,
                        department=base_booking.department,
                        chairman=base_booking.chairman,
                        presentation_file=base_booking.presentation_file,
                        room_layout=base_booking.room_layout,
                        room_layout_attachment=base_booking.room_layout_attachment
                    )
                    
                    restricted_names = ['RD 2', 'RD 4', 'TEIL', 'ห้องประชุมใหญ่']
                    is_restricted_room = False
                    for r_name in restricted_names:
                        if r_name.lower() in room.name.lower():
                            is_restricted_room = True
                            break
                    
                    if is_restricted_room or has_equipments or room.requires_approval:
                         new_b.status = 'PENDING'
                    else:
                         new_b.status = 'APPROVED'
                    
                    new_b.save()
                    
                    # [แก้ไข] เอาการบันทึก participants ออก
                    if 'equipments' in form.cleaned_data: new_b.equipments.set(form.cleaned_data['equipments'])

                    log_action(request, 'BOOKING_CREATED', new_b, f"จองห้อง {room.name}")
                    
                    if new_b.status == 'APPROVED':
                        token = get_valid_token(request.user, request)
                        if token:
                            try:
                                client = get_outlook_client(request)
                                evt = client.create_calendar_event(token, new_b)
                                new_b.outlook_event_id = evt['id']
                                new_b.save(update_fields=['outlook_event_id'])
                            except: pass
                    
                    if count == 0: 
                        subject = 'โปรดอนุมัติรายการใหม่' if new_b.status == 'PENDING' else 'มีการจองห้องประชุมใหม่'
                        send_booking_notification(new_b, '', subject)

                    count += 1

                messages.success(request, f"จองสำเร็จ {count} รายการ")
                return redirect('dashboard')
    else:
        form = BookingForm(initial={'room': room})
    
    return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})

@login_required
def master_calendar_view(request):
    ctx = get_base_context(request); ctx['all_rooms'] = Room.objects.all()
    return render(request, 'pages/master_calendar.html', ctx)

@login_required
def history_view(request):
    if is_admin(request.user):
        qs = Booking.objects.select_related('room', 'user').all()
    else:
        qs = Booking.objects.select_related('room').filter(user=request.user)

    date_filter = request.GET.get('date')
    room_filter = request.GET.get('room')
    status_filter = request.GET.get('status')

    if date_filter:
        qs = qs.filter(start_time__date=date_filter)
    
    if room_filter and room_filter.isdigit():
        qs = qs.filter(room_id=room_filter)

    if status_filter:
        qs = qs.filter(status=status_filter)

    room_list = Room.objects.all()

    context = {
        **get_base_context(request),
        'bookings_list': qs.order_by('-start_time'),
        'room_list': room_list,
        'selected_date': date_filter,
        'selected_room': int(room_filter) if room_filter and room_filter.isdigit() else None,
        'selected_status': status_filter,
        'current_time': timezone.now(),
    }

    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    can_edit = b.can_user_edit_or_cancel(request.user)
    return render(request, 'pages/booking_detail.html', {**get_base_context(request), 'booking': b, 'can_edit_or_cancel': can_edit})

# ----------------------------------------------------------------------
# D. CRUD & APPROVALS
# ----------------------------------------------------------------------

@login_required
def edit_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    if not b.can_user_edit_or_cancel(request.user):
        messages.error(request, "ไม่มีสิทธิ์แก้ไข")
        return redirect('history')
    
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=b)
        if form.is_valid():
            booking = form.save(commit=False)
            
            # [แก้ไข] ถ้าไม่ใช่ Admin แก้ไข -> เปลี่ยนเป็น PENDING
            if not is_approver_or_admin(request.user):
                booking.status = 'PENDING'
                booking.is_user_seen = False 
            
            booking.save()
            form.save_m2m()
            
            log_action(request, 'BOOKING_EDITED', booking, "แก้ไขการจอง")
            
            send_booking_notification(booking, '', 'แจ้งเตือน: มีการแก้ไขข้อมูลการจอง 📝')

            if booking.outlook_event_id and booking.status == 'APPROVED':
                token = get_valid_token(request.user, request)
                if token:
                    try:
                        client = get_outlook_client(request)
                        client.update_calendar_event(token, booking.outlook_event_id, booking)
                    except: pass

            messages.success(request, "บันทึกการแก้ไขเรียบร้อย")
            return redirect('history')
    else:
        form = BookingForm(instance=b)
    return render(request, 'pages/edit_booking.html', {**get_base_context(request), 'form': form, 'booking': b})

@login_required
@require_POST
def delete_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    if b.can_user_edit_or_cancel(request.user):
        if b.outlook_event_id:
            token = get_valid_token(request.user, request)
            if token:
                try:
                    client = get_outlook_client(request)
                    client.delete_calendar_event(token, b.outlook_event_id)
                except: pass
        
        b.status = 'CANCELLED'
        b.outlook_event_id = None
        b.is_user_seen = False 
        b.save()
        log_action(request, 'BOOKING_CANCELLED', b, "ยกเลิกการจอง")
        
        send_booking_notification(b, '', 'แจ้งเตือน: มีการยกเลิกการจอง ❌')

        messages.success(request, "ยกเลิกสำเร็จ และแจ้งเตือนแอดมินแล้ว")
    return redirect('history')

@login_required
def approvals_view(request):
    if not is_approver_or_admin(request.user): return redirect('dashboard')
    
    if is_admin(request.user):
        bookings = Booking.objects.filter(status='PENDING').select_related('room', 'user').order_by('start_time')
    else:
        bookings = Booking.objects.filter(room__approver=request.user, status='PENDING').select_related('room', 'user').order_by('start_time')
    
    return render(request, 'pages/approvals.html', {**get_base_context(request), 'pending_bookings': bookings})

@login_required
@require_POST
def approve_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    b.status = 'APPROVED'
    b.is_user_seen = False
    b.save()
    
    log_action(request, 'BOOKING_APPROVED', b, "อนุมัติโดย Admin")
    
    send_booking_notification(b, '', 'ผลการอนุมัติ: อนุมัติแล้ว ✅')
    
    token = get_valid_token(b.user, request)
    if token and not b.outlook_event_id:
        try:
            client = get_outlook_client(request)
            evt = client.create_calendar_event(token, b)
            b.outlook_event_id = evt['id']
            b.save(update_fields=['outlook_event_id'])
        except: pass
    
    messages.success(request, "อนุมัติเรียบร้อย และส่งแจ้งเตือนแล้ว")
    return redirect('approvals')

@login_required
@require_POST
def reject_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    b.status = 'REJECTED'
    b.is_user_seen = False
    b.save()
    
    log_action(request, 'BOOKING_REJECTED', b, "ปฏิเสธโดย Admin")
    
    send_booking_notification(b, '', 'ผลการอนุมัติ: ไม่อนุมัติ ❌')

    messages.success(request, "ปฏิเสธเรียบร้อย และส่งแจ้งเตือนแล้ว")
    return redirect('approvals')

# ----------------------------------------------------------------------
# E. ADMIN MANAGEMENT (Rooms & Users & Equipments)
# ----------------------------------------------------------------------

@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    return render(request, 'pages/rooms.html', {**get_base_context(request), 'rooms': Room.objects.all()})

@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกห้องประชุมเรียบร้อย")
            return redirect('rooms')
    else:
        form = RoomForm()
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form, 'title': 'เพิ่มห้อง'})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    r = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=r)
        if form.is_valid():
            form.save()
            messages.success(request, "แก้ไขข้อมูลห้องเรียบร้อย")
            return redirect('rooms')
    else:
        form = RoomForm(instance=r)
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form, 'title': 'แก้ไขห้อง'})

@login_required
@require_POST
def delete_room_view(request, room_id):
    Room.objects.filter(pk=room_id).delete()
    return redirect('rooms')

@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    return render(request, 'pages/user_management.html', {**get_base_context(request), 'users': User.objects.all()})

@login_required
@user_passes_test(is_admin)
def add_user_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มผู้ใช้แล้ว")
            return redirect('user_management')
    else:
        form = CustomUserCreationForm()
    return render(request, 'pages/user_form.html', {**get_base_context(request), 'form': form, 'title': 'เพิ่มผู้ใช้'})

@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    if request.method=='POST':
        u.groups.set(Group.objects.filter(pk__in=request.POST.getlist('groups')))
        u.is_staff = u.groups.filter(name='Admin').exists()
        u.is_superuser = u.is_staff
        u.save()
        return redirect('user_management')
    return render(request, 'pages/edit_user_roles.html', {**get_base_context(request), 'user_to_edit': u, 'all_groups': Group.objects.all()})

@login_required
@user_passes_test(is_admin)
def equipment_management_view(request):
    return render(request, 'pages/equipments.html', {**get_base_context(request), 'equipments': Equipment.objects.all().order_by('name')})

@login_required
@user_passes_test(is_admin)
def add_equipment_view(request):
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มอุปกรณ์เรียบร้อย")
            return redirect('equipments')
    else:
        form = EquipmentForm()
    return render(request, 'pages/equipment_form.html', {**get_base_context(request), 'form': form, 'title': 'เพิ่มอุปกรณ์'})

@login_required
@require_POST
def delete_equipment_view(request, eq_id):
    Equipment.objects.filter(pk=eq_id).delete()
    messages.success(request, "ลบอุปกรณ์แล้ว")
    return redirect('equipments')

@login_required
def audit_log_view(request):
    logs = AuditLog.objects.all()
    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'pages/audit_log.html', {**get_base_context(request), 'page_obj': page_obj})

# ----------------------------------------------------------------------
# F. APIS & REPORTS
# ----------------------------------------------------------------------

def bookings_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    room_id = request.GET.get('room_id')
    try:
        s_dt = parser.parse(start)
        e_dt = parser.parse(end)
        
        qs = Booking.objects.filter(start_time__lt=e_dt, end_time__gt=s_dt).exclude(status__in=['CANCELLED', 'REJECTED']).select_related('room', 'user')
        if room_id: qs = qs.filter(room_id=room_id)
        
        events = []
        now = timezone.now()
        for b in qs:
            user_name = b.user.get_full_name() if b.user else "ไม่ระบุ"
            
            if b.status == 'PENDING':
                bg, txt = '#ffc107', '#000000' # Yellow
            elif b.status == 'APPROVED':
                if b.end_time < now:
                    bg, txt = '#6c757d', '#ffffff' # Grey (Past)
                elif b.start_time <= now <= b.end_time:
                    bg, txt = '#0d6efd', '#ffffff' # Blue (Current)
                else:
                    bg, txt = '#198754', '#ffffff' # Green (Future)
            else:
                bg, txt = '#dc3545', '#ffffff'

            events.append({
                'id': b.id,
                'title': b.title,
                'start': b.start_time.isoformat(),
                'end': b.end_time.isoformat(),
                'resourceId': b.room.id,
                'display': 'block',
                'backgroundColor': bg,
                'borderColor': bg,
                'textColor': txt,
                'extendedProps': {
                    'status': b.status, 
                    'user': user_name, 
                    'room': b.room.name,
                    'created_by': b.user.username if b.user else ''
                }
            })
        return JsonResponse(events, safe=False)
    except Exception as e:
        print(f"API Error: {e}")
        return JsonResponse([], safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, pk=data.get('id'))
        
        if not (booking.user == request.user or is_admin(request.user)):
            return JsonResponse({'status': 'error', 'message': 'ไม่มีสิทธิ์แก้ไขรายการนี้'}, status=403)
        
        start_dt = parser.parse(data.get('start'))
        end_str = data.get('end')
        if end_str: 
            end_dt = parser.parse(end_str)
        else: 
            end_dt = start_dt + (booking.end_time - booking.start_time)
        
        # --- ตรวจสอบเวลาจอง ---
        now = timezone.now()
        if start_dt < now:
             return JsonResponse({'status': 'error', 'message': 'ไม่สามารถจองย้อนหลังได้'}, status=400)
        if start_dt < now + timedelta(minutes=30):
             return JsonResponse({'status': 'error', 'message': 'ต้องจองล่วงหน้าอย่างน้อย 30 นาที'}, status=400)
        
        buffer_time = timedelta(minutes=30)
        is_overlap = Booking.objects.filter(
            room=booking.room,
            start_time__lt=end_dt + buffer_time,
            end_time__gt=start_dt - buffer_time,
            status__in=['APPROVED', 'PENDING']
        ).exclude(id=booking.id).exists()

        if is_overlap:
            return JsonResponse({'status': 'error', 'message': 'ช่วงเวลานี้มีคนจองแล้ว (หรือติดระยะเวลาพักห้อง 30 นาที)'}, status=400)

        booking.start_time = start_dt
        booking.end_time = end_dt
        
        # [แก้ไข] เปลี่ยนเป็น PENDING ถ้าลากแก้
        if not is_approver_or_admin(request.user):
            booking.status = 'PENDING'
            booking.is_user_seen = False
            
        booking.save()
        
        send_booking_notification(booking, '', 'แจ้งเตือน: มีการย้ายเวลาการจอง 🕒')
        
        if booking.outlook_event_id and booking.status == 'APPROVED':
            token = get_valid_token(request.user, request)
            if token:
                try:
                    client = get_outlook_client(request)
                    client.update_calendar_event(token, booking.outlook_event_id, booking)
                except: pass

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id):
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        
        if not booking.can_user_edit_or_cancel(request.user):
             return JsonResponse({'status': 'error', 'message': 'ไม่มีสิทธิ์ลบรายการนี้'}, status=403)
        
        if booking.outlook_event_id:
             token = get_valid_token(request.user, request)
             if token:
                 try:
                     client = get_outlook_client(request)
                     client.delete_calendar_event(token, booking.outlook_event_id)
                 except: pass

        booking.status = 'CANCELLED'
        booking.outlook_event_id = None
        booking.is_user_seen = False 
        booking.save()
        
        log_action(request, 'BOOKING_CANCELLED', booking, "ยกเลิกการจองผ่านปฏิทิน")
        
        send_booking_notification(booking, '', 'แจ้งเตือน: มีการยกเลิกการจอง ❌')
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def api_pending_count(request):
    count = 0
    latest_booking = None
    if is_approver_or_admin(request.user):
        if is_admin(request.user):
            pending_qs = Booking.objects.filter(status='PENDING').order_by('-created_at')
        else:
            pending_qs = Booking.objects.filter(room__approver=request.user, status='PENDING').order_by('-created_at')
        pending_count = pending_qs.count()
        
        cancel_qs = Booking.objects.filter(
            status='CANCELLED',
            updated_at__gte=timezone.now() - timedelta(days=1),
            is_user_seen=False
        )
        cancel_count = cancel_qs.count()
        
        count = pending_count + cancel_count

        if cancel_qs.exists():
            last_cancel = cancel_qs.order_by('-updated_at').first()
            latest_booking = {
                'id': last_cancel.id,
                'title': "มีการยกเลิกการจอง",
                'msg': f"ห้อง {last_cancel.room.name} ถูกยกเลิก"
            }
        elif pending_qs.exists():
             new_b = pending_qs.filter(created_at__gte=timezone.now() - timedelta(seconds=10)).first()
             if new_b:
                latest_booking = {
                    'id': new_b.id,
                    'title': "มีรายการขอจองใหม่",
                    'msg': f"ห้อง {new_b.room.name} โดย {new_b.user.username}"
                }
    else:
        count = Booking.objects.filter(user=request.user, is_user_seen=False).exclude(status='PENDING').count()
        
        updated_qs = Booking.objects.filter(
            user=request.user,
            updated_at__gte=timezone.now() - timedelta(seconds=10)
        ).exclude(status='PENDING')

        if updated_qs.exists():
            new_b = updated_qs.first()
            status_msg = "อนุมัติแล้ว" if new_b.status == 'APPROVED' else "ถูกปฏิเสธ"
            latest_booking = {
                'id': new_b.id,
                'title': f"ผลการจอง: {status_msg}",
                'msg': f"ห้อง {new_b.room.name} ({new_b.title})"
            }

    return JsonResponse({'count': count, 'latest_booking': latest_booking})

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    period = request.GET.get('period', 'monthly')
    dept_filter = request.GET.get('department', '')
    today = timezone.now().date()
    
    if period == 'daily':
        start_date = today
        report_title = f"สถิติประจำวันที่ {today.strftime('%d/%m/%Y')}"
    elif period == 'weekly':
        start_date = today - timedelta(days=7)
        report_title = f"สถิติย้อนหลัง 7 วัน"
    else:
        start_date = today - timedelta(days=30)
        report_title = f"สถิติย้อนหลัง 30 วัน"

    bookings_qs = Booking.objects.filter(start_time__date__gte=start_date, status='APPROVED')
    if dept_filter:
        bookings_qs = bookings_qs.filter(department=dept_filter)

    room_stats = bookings_qs.values('room__name').annotate(count=Count('id')).order_by('-count')[:10]
    room_labels = [item['room__name'] for item in room_stats]
    room_data = [item['count'] for item in room_stats]

    dept_labels = []
    dept_data = []
    all_departments = []
    try:
        all_departments = Booking.objects.exclude(department__isnull=True).exclude(department__exact='').values_list('department', flat=True).distinct().order_by('department')
        dept_stats = bookings_qs.values('department').annotate(count=Count('id')).order_by('-count')[:10]
        dept_labels = [item['department'] for item in dept_stats if item['department']]
        dept_data = [item['count'] for item in dept_stats if item['department']]
    except Exception as e:
        print(f"Dept Stats Error: {e}")

    context = get_base_context(request)
    context.update({
        'room_usage_labels': json.dumps(room_labels), 
        'room_usage_data': json.dumps(room_data),
        'dept_usage_labels': json.dumps(dept_labels),
        'dept_usage_data': json.dumps(dept_data),
        'all_departments': all_departments,
        'current_period': period,
        'current_department': dept_filter,
        'report_title': report_title,
        'total_rooms_count': Room.objects.count(),
        'today_bookings_count': Booking.objects.filter(start_time__date=today, status='APPROVED').count(),
        'pending_count': Booking.objects.filter(status='PENDING').count(),
        'total_users_count': User.objects.count()
    })
    return render(request, 'pages/reports.html', context)

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="booking_report.csv"'
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['วันที่', 'เวลา', 'หัวข้อ', 'ห้อง', 'ผู้จอง'])
    for b in Booking.objects.all().select_related('room', 'user').order_by('-start_time'):
        user_name = b.user.username if b.user else "ไม่ระบุ"
        writer.writerow([
            b.start_time.strftime('%Y-%m-%d'), 
            b.start_time.strftime('%H:%M'), 
            b.title, 
            b.room.name, 
            user_name
        ])
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    if HTML is None:
        messages.error(request, "ระบบ PDF ไม่พร้อมใช้งาน")
        return redirect('reports')
    bookings = Booking.objects.filter(status__in=['APPROVED', 'PENDING']).select_related('room', 'user').order_by('-start_time')
    
    context = {
        'bookings': bookings, 
        'export_date': timezone.now(),
        'user': request.user,
        'report_title': 'รายงานการจองห้องประชุม'
    }
    
    html_string = render_to_string('pages/reports_pdf.html', context)
    try:
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"PDF Error: {e}")
        return redirect('reports')

@csrf_exempt
def teams_action_receiver(request): return HttpResponse(status=200)