import json
import re
import csv
import uuid
import os
import base64
from datetime import datetime, timedelta, time
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from dateutil import parser

from thefuzz import process
import dateparser

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
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache 
from django.contrib.staticfiles import finders

from dal import autocomplete
from dal_select2.views import Select2QuerySetView

from xhtml2pdf import pisa
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.models import TextSendMessage, MessageEvent, TextMessage
    from linebot.exceptions import InvalidSignatureError
except ImportError:
    LineBotApi = None
    WebhookHandler = None

from .models import Room, Booking, AuditLog, OutlookToken, UserProfile, Equipment
from .forms import BookingForm, RoomForm, CustomUserCreationForm, CustomUserEditForm, EquipmentForm
from .outlook_client import OutlookClient

line_bot_api = None
handler = None
if hasattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN') and hasattr(settings, 'LINE_CHANNEL_SECRET'):
    try:
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
    except: pass

# =============================================================
# Helper Functions
# =============================================================
def link_callback(uri, rel):
    sUrl = settings.STATIC_URL
    mUrl = settings.MEDIA_URL
    path = ""

    if uri.startswith(mUrl):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(mUrl, ""))
    elif uri.startswith(sUrl):
        target_file = uri.replace(sUrl, "").lstrip('/')
        path = finders.find(target_file)
        if not path:
            path = os.path.join(settings.BASE_DIR, 'static', target_file)

    if not path or not os.path.isfile(path):
        return "" 
        
    return path

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff or user.groups.filter(name='Admin').exists())

def is_approver_or_admin(user):
    return is_admin(user)

def get_admin_emails():
    return list(User.objects.filter(Q(groups__name='Admin') | Q(is_superuser=True) | Q(is_staff=True), is_active=True).distinct().exclude(email__exact='').values_list('email', flat=True))

def log_action(request, action_key, target_obj=None, detail_text=""):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
        full_details = detail_text
        if target_obj: full_details = f"{detail_text} [Target: {target_obj}]"
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action_key,
            details=full_details,
            ip_address=ip
        )
    except Exception as e: print(f"Log Error: {e}")

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
                if 'refresh_token' in new_tokens: token_obj.refresh_token = new_tokens['refresh_token']
                token_obj.expires_at = timezone.now() + timedelta(seconds=new_tokens['expires_in'])
                token_obj.save()
            except: return None
        return token_obj.access_token
    except OutlookToken.DoesNotExist: return None

def get_base_context(request):
    current_url_name = request.resolver_match.url_name if request.resolver_match else ''
    is_admin_user = is_admin(request.user)
    
    show_approvals = is_admin_user

    menu_structure = [
        {'label': 'หน้าหลัก', 'url_name': 'dashboard', 'icon': 'bi-house-fill', 'show': request.user.is_authenticated},
        {'label': 'ปฏิทินรวม', 'url_name': 'master_calendar', 'icon': 'bi-calendar3-range', 'show': request.user.is_authenticated},
        {'label': 'ประวัติการจอง', 'url_name': 'history', 'icon': 'bi-clock-history', 'show': request.user.is_authenticated},
        {'label': 'รออนุมัติ', 'url_name': 'approvals', 'icon': 'bi-check2-circle', 'show': show_approvals},
    ]
    admin_menu_structure = [
        {'label': 'จัดการห้องประชุม', 'url_name': 'rooms', 'icon': 'bi-door-open-fill', 'show': is_admin_user},
        {'label': 'จัดการอุปกรณ์', 'url_name': 'equipments', 'icon': 'bi-tools', 'show': is_admin_user}, 
        {'label': 'จัดการผู้ใช้งาน', 'url_name': 'user_management', 'icon': 'bi-people-fill', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'url_name': 'reports', 'icon': 'bi-bar-chart-fill', 'show': is_admin_user},
        {'label': 'ประวัติการใช้งาน', 'url_name': 'audit_log', 'icon': 'bi-clipboard-data-fill', 'show': is_admin_user},
    ]

    menu_items = [m for m in menu_structure if m['show']]
    for m in menu_items: m['active'] = (m['url_name'] == current_url_name)

    admin_menu_items = [m for m in admin_menu_structure if m['show']]
    for m in admin_menu_items: m['active'] = (m['url_name'] == current_url_name)

    pending_count = 0
    pending_notifications = []
    
    if request.user.is_authenticated:
        if is_admin(request.user):
            qs = Booking.objects.filter(
                Q(status='PENDING') | Q(status='CANCELLED'), 
                is_user_seen=False
            ).select_related('room', 'user').order_by('-updated_at')
            
            pending_notifications = qs[:15]
            pending_count = qs.count()
            
            recent_cancellations = [] 
        else:
            qs = Booking.objects.filter(user=request.user, is_user_seen=False).exclude(status='PENDING').select_related('room').order_by('-updated_at')
            pending_count = qs.count()
            pending_notifications = qs
            recent_cancellations = []
    else:
        recent_cancellations = []

    return {
        'menu_items': menu_items,
        'admin_menu_items': admin_menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,
        'pending_notifications': pending_notifications,
        'recent_cancellations': recent_cancellations,
        'login_form': AuthenticationForm(),
    }

def send_booking_notification(booking, template_name, subject_prefix):
    equip_text = "-"
    if hasattr(booking, 'equipments') and booking.equipments.exists():
        equip_names = [eq.name for eq in booking.equipments.all()]
        equip_text = ", ".join(equip_names)

    note_text = booking.additional_requests if booking.additional_requests else "-"
    
    local_start = timezone.localtime(booking.start_time)
    local_end = timezone.localtime(booking.end_time)
    
    start_str = local_start.strftime('%d/%m/%Y %H:%M')
    end_str = local_end.strftime('%H:%M')
    
    user_name = booking.user.get_full_name() or booking.user.username

    layout_line = ""
    if booking.room.name == 'ห้องประชุมใหญ่':
        layout_display = booking.get_room_layout_display()
        if booking.room_layout == 'other' and booking.room_layout_attachment:
            layout_display += f" (ไฟล์แนบ: {booking.room_layout_attachment.url})"
        layout_line = f"รูปแบบ: {layout_display}\n"

    link_line = ""
    if booking.presentation_link:
        link_line = f"ลิงก์เอกสาร: {booking.presentation_link}\n"

    msg = (f"{subject_prefix}\n"
           f"ผู้จอง: {user_name}\n"
           f"ห้อง: {booking.room.name}\n"
           f"เรื่อง: {booking.title}\n"
           f"เวลา: {start_str} - {end_str}\n"
           f"จำนวนคน: {booking.participant_count} คน\n"
           f"{layout_line}"
           f"{link_line}"
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
        
        admins = User.objects.filter(
            Q(is_superuser=True) | 
            Q(is_staff=True) | 
            Q(groups__name='Admin')
        ).distinct()

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

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.filter(is_active=True).order_by('first_name', 'username')
        if self.q:
            qs = qs.filter(Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q))
        return qs[:15]

class EquipmentAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return Equipment.objects.none()
        qs = Equipment.objects.filter(is_active=True).order_by('name')
        if self.q: qs = qs.filter(name__icontains=self.q)
        return qs

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            log_action(request, 'LOGIN', None, "เข้าสู่ระบบสำเร็จ")
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url: return redirect(next_url)
            return redirect('dashboard')
        else: messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else: form = AuthenticationForm()
    return render(request, 'login_card.html', {'form': form})

def public_calendar_view(request):
    all_rooms = Room.objects.all()
    context = get_base_context(request)
    context.update({'all_rooms': all_rooms, 'is_public_view': True})
    return render(request, 'pages/master_calendar.html', context)

@login_required
def logout_view(request):
    log_action(request, 'LOGOUT', None, "ออกจากระบบ")
    logout(request)
    return redirect('public_calendar') 

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
            OutlookToken.objects.update_or_create(user=request.user, defaults={'access_token': tokens['access_token'], 'refresh_token': tokens.get('refresh_token'), 'expires_at': exp})
            log_action(request, 'LOGIN', None, "เชื่อมต่อ Outlook สำเร็จ")
            messages.success(request, "เชื่อมต่อ Outlook สำเร็จ!")
        except Exception as e: messages.error(request, f"Error: {e}")
    return redirect('dashboard')

@login_required 
def smart_search_view(request):
    query = request.GET.get('q')
    rooms = Room.objects.all().order_by('name')
    search_message = []
    alert_type = "info"
    ctx = get_base_context(request) 

    if not query:
        ctx.update({
            'available_rooms': rooms,
            'search_message': "พิมพ์ค้นหาได้เลยครับ (เช่น '10 คนบ่ายนี้', 'ห้องว่างพรุ่งนี้มีไมค์')",
            'alert_type': 'light'
        })
        return render(request, 'pages/search_results.html', ctx)

    clean_query = query.strip()
    clean_query = re.sub(r'(\d+)', r' \1 ', clean_query)
    time_keywords_list = ['เช้า', 'บ่าย', 'เย็น', 'พรุ่งนี้', 'มะรืน', 'วันนี้', 'จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'ศุกร์']
    for kw in time_keywords_list: clean_query = clean_query.replace(kw, f" {kw} ")
    clean_query = re.sub(r'\s+', ' ', clean_query).strip()

    numbers = re.findall(r'\d+', clean_query)
    if numbers:
        wanted_capacity = max([int(n) for n in numbers])
        rooms = rooms.filter(capacity__gte=wanted_capacity)
        search_message.append(f"👥 รองรับ {wanted_capacity} คน+")
        clean_query = re.sub(r'\d+', '', clean_query)

    target_date = timezone.now().date()
    is_date_found = False
    
    if 'พรุ่งนี้' in clean_query:
        target_date = timezone.now().date() + timedelta(days=1)
        is_date_found = True
        clean_query = clean_query.replace('พรุ่งนี้', '')
    elif 'มะรืน' in clean_query:
        target_date = timezone.now().date() + timedelta(days=2)
        is_date_found = True
        clean_query = clean_query.replace('มะรืน', '')
    elif 'วันนี้' in clean_query or 'นี้' in clean_query:
        target_date = timezone.now().date()
        clean_query = clean_query.replace('วันนี้', '').replace('นี้', '')
    else:
        try:
            parsed = dateparser.parse(clean_query, settings={'PREFER_DATES_FROM': 'future'})
            if parsed and parsed.date() != timezone.now().date():
                target_date = parsed.date()
                is_date_found = True
        except: pass

    if is_date_found: search_message.append(f"📅 วันที่ {target_date.strftime('%d/%m/%Y')}")

    start_time = None; end_time = None
    if 'เช้า' in clean_query:
        start_time = time(8, 0); end_time = time(12, 0)
        search_message.append("🕒 ช่วงเช้า (08:00-12:00)")
        clean_query = clean_query.replace('เช้า', '')
    elif 'บ่าย' in clean_query:
        start_time = time(13, 0); end_time = time(17, 0)
        search_message.append("🕒 ช่วงบ่าย (13:00-17:00)")
        clean_query = clean_query.replace('บ่าย', '')
    elif 'เย็น' in clean_query:
        start_time = time(17, 0); end_time = time(20, 0)
        search_message.append("🕒 ช่วงเย็น (17:00-20:00)")
        clean_query = clean_query.replace('เย็น', '')

    if start_time and end_time:
        dt_start = datetime.combine(target_date, start_time)
        dt_end = datetime.combine(target_date, end_time)
        busy_rooms = Booking.objects.filter(start_time__lt=dt_end, end_time__gt=dt_start, status__in=['APPROVED', 'PENDING']).values_list('room_id', flat=True)
        rooms = rooms.exclude(id__in=busy_rooms)

    clean_query = clean_query.strip()
    
    if clean_query and len(clean_query) > 1:
        name_filter = Q(name__icontains=clean_query) | Q(location__icontains=clean_query)
        rooms = rooms.filter(name_filter)
        search_message.append(f"🔎 คำค้นหา: {clean_query}")

    final_msg = " | ".join(search_message) if search_message else "แสดงห้องทั้งหมด"
    if not rooms.exists():
        alert_type = "warning"
        final_msg += " (ไม่พบห้องที่ตรงตามเงื่อนไข ลองลดเงื่อนไขดูนะครับ)"

    ctx.update({'query': query, 'available_rooms': rooms, 'search_count': rooms.count(), 'search_message': final_msg, 'alert_type': alert_type})
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
        r.is_under_maintenance = r.is_currently_under_maintenance 
        
        if r.is_under_maintenance: r.status, r.status_class = 'ปิดปรับปรุง', 'bg-secondary text-white'
        elif current_booking:
            if current_booking.status == 'PENDING': r.status, r.status_class = 'รออนุมัติ', 'bg-warning text-dark'
            else: r.status, r.status_class = 'ไม่ว่าง', 'bg-danger text-white'
        else: r.status, r.status_class = 'ว่าง', 'bg-success text-white'
        rooms_processed.append(r)

    if sort_by == 'status':
        status_priority = {'ว่าง': 0, 'รออนุมัติ': 1, 'ไม่ว่าง': 2, 'ปิดปรับปรุง': 3}
        rooms_processed.sort(key=lambda x: status_priority.get(x.status, 99))
    elif sort_by == 'capacity': rooms_processed.sort(key=lambda x: x.capacity, reverse=True)
    elif sort_by == 'name': rooms_processed.sort(key=lambda x: x.name)
    else: rooms_processed.sort(key=lambda x: (x.building or '', str(x.floor or ''), x.name))

    for r in rooms_processed: buildings[r.building or "อาคารทั่วไป"].append(r)

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
def master_calendar_view(request):
    ctx = get_base_context(request); ctx['all_rooms'] = Room.objects.all()
    return render(request, 'pages/master_calendar.html', ctx)

@login_required
@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            booking_start = form.cleaned_data.get('start_time')
            now = timezone.now()

            # --- ตรวจสอบสิทธิ์ Admin และกฎการจอง ---
            is_user_admin = is_admin(request.user)

            if booking_start < now:
                messages.error(request, "ไม่สามารถจองย้อนหลังได้ กรุณาเลือกเวลาใหม่")
                return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})

            if not is_user_admin:  # กฎ 30 นาที (ยกเว้นให้ Admin)
                if booking_start < now + timedelta(minutes=30):
                    messages.error(request, "กรุณาจองล่วงหน้าอย่างน้อย 30 นาที เพื่อเตรียมห้องและอุปกรณ์")
                    return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})
            
            # ------------------------------------
            
            recurrence = form.cleaned_data.get('recurrence')
            recurrence_end_date = form.cleaned_data.get('recurrence_end_date')

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
                
                # ตรวจสอบการจองซ้ำ (Buffer 30 นาที)
                buffer_time = timedelta(minutes=30)
                is_overlap = Booking.objects.filter(
                    room=room, 
                    start_time__lt=current_end + buffer_time, 
                    end_time__gt=current_start - buffer_time,
                    status__in=['APPROVED', 'PENDING']
                ).exclude(id=base_booking.id).exists()
                
                if is_overlap:
                    conflict_dates.append(f"{current_start.strftime('%d/%m/%Y %H:%M')}")
                
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
                        presentation_link=base_booking.presentation_link, 
                        room_layout=base_booking.room_layout,
                        room_layout_attachment=base_booking.room_layout_attachment,
                        booking_type=base_booking.booking_type 
                    )
                    
                    if 'ใหญ่' not in room.name:
                        new_b.room_layout = ''

                    # ถ้าเป็น Admin หรือแม่บ้านทำความสะอาด -> อนุมัติทันที
                    if is_user_admin or new_b.booking_type == 'cleaning':
                        new_b.status = 'APPROVED'
                    else:
                        new_b.status = 'PENDING'
                        
                    new_b.is_user_seen = False
                    new_b.save()
                    
                    if 'equipments' in form.cleaned_data: 
                        new_b.equipments.set(form.cleaned_data['equipments'])

                    log_action(request, 'BOOKING_CREATED', new_b, f"จองห้อง {room.name}")
                    
                    # ส่งแจ้งเตือน
                    if count == 0: 
                        subject = 'โปรดอนุมัติรายการใหม่' if new_b.status == 'PENDING' else 'มีการจองห้องประชุมใหม่'
                        send_booking_notification(new_b, '', subject)

                    count += 1

                messages.success(request, f"จองสำเร็จ {count} รายการ")
                return redirect('dashboard')
    else:
        initial_data = {'room': room}
        try:
            if hasattr(request.user, 'profile') and request.user.profile.department:
                initial_data['department'] = request.user.profile.department
        except: pass
            
        form = BookingForm(initial=initial_data)
    
    return render(request, 'pages/room_calendar.html', {**get_base_context(request), 'room': room, 'form': form})

@login_required
def booking_detail_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    
    is_owner = (request.user == b.user)
    is_admin_user = is_admin(request.user)
    needs_update = False

    if is_admin_user and b.status in ['PENDING', 'CANCELLED']:
        needs_update = True

    if is_owner and b.status in ['APPROVED', 'REJECTED', 'CANCELLED']:
        needs_update = True

    if needs_update and not b.is_user_seen:
        b.is_user_seen = True
        b.save(update_fields=['is_user_seen'])

    can_edit = b.can_user_edit_or_cancel(request.user)
    return render(request, 'pages/booking_detail.html', {**get_base_context(request), 'booking': b, 'can_edit_or_cancel': can_edit})

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
def history_view(request):
    if is_admin(request.user): qs = Booking.objects.select_related('room', 'user').all()
    else: qs = Booking.objects.select_related('room').filter(user=request.user)

    date_filter = request.GET.get('date')
    room_filter = request.GET.get('room')
    status_filter = request.GET.get('status')

    if date_filter: qs = qs.filter(start_time__date=date_filter)
    if room_filter and room_filter.isdigit(): qs = qs.filter(room_id=room_filter)
    if status_filter: qs = qs.filter(status=status_filter)

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
def approvals_view(request):
    if not is_admin(request.user): return redirect('dashboard')
    bookings = Booking.objects.filter(status='PENDING').select_related('room', 'user').order_by('start_time')
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

@login_required
@user_passes_test(is_admin)
def room_management_view(request): return render(request, 'pages/rooms.html', {**get_base_context(request), 'rooms': Room.objects.all()})
@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid(): form.save(); messages.success(request, "บันทึกห้องประชุมเรียบร้อย"); return redirect('rooms')
    else: form = RoomForm()
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    r = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=r)
        if form.is_valid():
            # บันทึกข้อมูลตามปกติ ค่าจากสวิตซ์ Active ใน HTML จะถูกส่งมาและบันทึกเอง
            room_obj = form.save()
            
            if form.cleaned_data.get('is_cleaning'):
                Booking.objects.create(
                    room=r,
                    user=request.user,
                    title="แม่บ้านทำความสะอาด",
                    booking_type='cleaning',
                    start_time=form.cleaned_data['cleaning_start'],
                    end_time=form.cleaned_data['cleaning_end'],
                    participant_count=1,
                    status='APPROVED',
                    is_user_seen=True
                )
                messages.success(request, "บันทึกห้องและสร้างรายการทำความสะอาดเรียบร้อย")
            else:
                messages.success(request, "แก้ไขข้อมูลห้องเรียบร้อย")
            return redirect('rooms')
    else:
        form = RoomForm(instance=r)
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form})

# [เพิ่มฟังก์ชันที่ขาดไป] ลบห้องประชุม
@login_required
@user_passes_test(is_admin)
@require_POST
def delete_room_view(request, room_id):
    Room.objects.filter(pk=room_id).delete()
    messages.success(request, "ลบห้องประชุมเรียบร้อยแล้ว")
    return redirect('rooms')

@login_required
@user_passes_test(is_admin)
def open_room_view(request, room_id):
    r = get_object_or_404(Room, pk=room_id)
    r.is_maintenance = False 
    r.maintenance_start = None
    r.maintenance_end = None
    r.save()
    messages.success(request, f"เปิดใช้งานห้อง {r.name} เรียบร้อยแล้ว")
    return redirect('dashboard')

@login_required
@user_passes_test(is_admin)
def user_management_view(request): return render(request, 'pages/user_management.html', {**get_base_context(request), 'users': User.objects.all()})

@login_required
@user_passes_test(is_admin)
def add_user_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มผู้ใช้งานเรียบร้อยแล้ว")
            return redirect('user_management')
    else:
        form = CustomUserCreationForm()

    return render(request, 'pages/user_form.html', {
        **get_base_context(request), 
        'form': form
    })

@login_required
@user_passes_test(is_admin)
def edit_user_view(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        form = CustomUserEditForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            messages.success(request, f"แก้ไขข้อมูล {u.username} เรียบร้อย")
            return redirect('user_management')
    else:
        form = CustomUserEditForm(instance=u)

    return render(request, 'pages/user_form.html', {
        **get_base_context(request), 
        'form': form
    })

@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        selected_groups = request.POST.getlist('groups')
        u.groups.set(Group.objects.filter(pk__in=selected_groups))
        is_admin_group = u.groups.filter(name='Admin').exists()
        u.is_staff = is_admin_group
        u.is_superuser = is_admin_group
        u.save()
        return redirect('user_management')
    available_groups = Group.objects.filter(name='Admin')
    return render(request, 'pages/edit_user_roles.html', {**get_base_context(request), 'user_to_edit': u, 'all_groups': available_groups})

@login_required
@user_passes_test(is_admin)
def equipment_management_view(request): return render(request, 'pages/equipments.html', {**get_base_context(request), 'equipments': Equipment.objects.all()})
@login_required
@user_passes_test(is_admin)
def add_equipment_view(request):
    if request.method=='POST':
        form=EquipmentForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "เพิ่มอุปกรณ์เรียบร้อย"); return redirect('equipments')
    else: form=EquipmentForm()
    return render(request, 'pages/equipment_form.html', {**get_base_context(request), 'form': form})
@login_required
@user_passes_test(is_admin)
def edit_equipment_view(request, eq_id):
    eq=get_object_or_404(Equipment, pk=eq_id)
    if request.method=='POST':
        form=EquipmentForm(request.POST,instance=eq)
        if form.is_valid(): form.save(); messages.success(request, "แก้ไขข้อมูลอุปกรณ์เรียบร้อย"); return redirect('equipments')
    else: form=EquipmentForm(instance=eq)
    return render(request, 'pages/equipment_form.html', {**get_base_context(request), 'form': form})
@login_required
@require_POST
def delete_equipment_view(request, eq_id): Equipment.objects.filter(pk=eq_id).delete(); messages.success(request, "ลบอุปกรณ์แล้ว"); return redirect('equipments')

@login_required
def audit_log_view(request):
    logs = AuditLog.objects.all().order_by('-timestamp')
    paginator = Paginator(logs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'pages/audit_log.html', {**get_base_context(request), 'page_obj': page_obj})

@login_required
@never_cache
def api_pending_count(request):
    count = 0
    notifications_data = []
    
    if is_admin(request.user):
        pending_qs = Booking.objects.filter(status='PENDING', is_user_seen=False).select_related('room', 'user').order_by('-created_at')
        count = pending_qs.count()
        
        cancel_qs = Booking.objects.filter(status='CANCELLED', is_user_seen=False, updated_at__gte=timezone.now() - timedelta(days=1)).select_related('room', 'user').order_by('-updated_at')
        count += cancel_qs.count()

        for item in pending_qs[:5]:
            date_str = item.start_time.strftime('%d/%m')
            notifications_data.append({
                'title': f"ขอจอง: {item.room.name} ({date_str})",
                'user': item.user.get_full_name(),
                'time': item.created_at.strftime('%H:%M'),
                'url': reverse('booking_detail', args=[item.id]),
                'status': 'pending',
                'is_seen': False
            })
            
        if len(notifications_data) < 5:
            remaining = 5 - len(notifications_data)
            for item in cancel_qs[:remaining]:
                date_str = item.start_time.strftime('%d/%m')
                notifications_data.append({
                    'title': f"ยกเลิก: {item.room.name} ({date_str})",
                    'user': item.user.get_full_name(),
                    'time': item.updated_at.strftime('%H:%M'),
                    'url': reverse('booking_detail', args=[item.id]),
                    'status': 'cancelled',
                    'is_seen': False
                })
    else:
        updated_qs = Booking.objects.filter(user=request.user, is_user_seen=False).exclude(status='PENDING').select_related('room').order_by('-updated_at')
        count = updated_qs.count()
        
        for item in updated_qs[:5]:
            status_text = "อนุมัติ" if item.status == 'APPROVED' else "ปฏิเสธ"
            if item.status == 'CANCELLED': status_text = "ยกเลิก"
            
            date_str = item.start_time.strftime('%d/%m')
            notifications_data.append({
                'title': f"{status_text}: {item.title} ({date_str})", 
                'user': item.room.name,
                'time': item.updated_at.strftime('%H:%M'),
                'url': reverse('booking_detail', args=[item.id]),
                'status': item.status.lower(),
                'is_seen': False
            })

    return JsonResponse({'count': count, 'notifications': notifications_data})

@never_cache
def bookings_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    room_id = request.GET.get('room_id')
    
    is_user_logged_in = request.user.is_authenticated

    try:
        s_dt = parser.parse(start)
        e_dt = parser.parse(end)
        
        qs = Booking.objects.filter(start_time__lt=e_dt, end_time__gt=s_dt).select_related('room', 'user')
        if room_id: qs = qs.filter(room_id=room_id)
        
        events = []
        now = timezone.now()
        
        for b in qs:
            user_name = b.user.get_full_name() if b.user else "ไม่ระบุ"
            
            if b.booking_type == 'cleaning':
                bg, txt = '#0dcaf0', '#000000' # สี Cyan, ตัวดำ
            elif b.status == 'PENDING': 
                bg, txt = '#ffc107', '#000000'
            elif b.status == 'APPROVED':
                if b.end_time < now: bg, txt = '#6c757d', '#ffffff'
                elif b.start_time <= now <= b.end_time: bg, txt = '#0d6efd', '#ffffff'
                else: bg, txt = '#198754', '#ffffff'
            elif b.status == 'REJECTED': bg, txt = '#FF4848', '#ffffff' 
            elif b.status == 'CANCELLED': bg, txt = '#fd7e14', '#ffffff'
            else: bg, txt = '#6c757d', '#ffffff'

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
                'editable': is_user_logged_in and b.status not in ['CANCELLED', 'REJECTED'] and (b.end_time > now),
                'extendedProps': {
                    'status': b.status, 
                    'booking_type': b.booking_type,
                    'user': user_name, 
                    'room': b.room.name,
                    'created_by': b.user.username if b.user else ''
                }
            })

        rooms_to_check = Room.objects.all()
        if room_id:
            rooms_to_check = rooms_to_check.filter(id=room_id)

        for r in rooms_to_check:
            if r.is_currently_under_maintenance:
                real_start = start
                real_end = end

                if hasattr(r, 'maintenance_start') and r.maintenance_start:
                    real_start = r.maintenance_start.isoformat()
                
                if hasattr(r, 'maintenance_end') and r.maintenance_end:
                    real_end = r.maintenance_end.isoformat()

                events.append({
                    'id': f"maint_{r.id}",
                    'title': '⛔ ปิดปรับปรุง',
                    'start': real_start, 
                    'end': real_end,     
                    'resourceId': r.id,
                    'display': 'block', 
                    'backgroundColor': '#212529',
                    'borderColor': '#000000',
                    'textColor': '#ffffff',
                    'allDay': False,
                    'editable': False, 
                    'extendedProps': {
                        'status': 'MAINTENANCE', 
                        'booking_type': 'maintenance',
                        'user': 'System', 
                        'room': r.name,
                        'created_by': 'Admin'
                    }
                })
        
        return JsonResponse(events, safe=False)
        
    except Exception as e: 
        print(f"Calendar Error: {e}")
        return JsonResponse([], safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, pk=data.get('id'))
        if not (booking.user == request.user or is_admin(request.user)):
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
        start_dt = parser.parse(data.get('start'))
        if data.get('end'):
            end_dt = parser.parse(data.get('end'))
        else:
            duration = booking.end_time - booking.start_time
            end_dt = start_dt + duration

        now = timezone.now()
        if start_dt < now: return JsonResponse({'status': 'error', 'message': 'ไม่สามารถจองย้อนหลังได้'}, status=400)
        if start_dt < now + timedelta(minutes=30): return JsonResponse({'status': 'error', 'message': 'ต้องจองล่วงหน้า 30 นาที'}, status=400)
        
        buffer_time = timedelta(minutes=30)
        is_overlap = Booking.objects.filter(room=booking.room, start_time__lt=end_dt + buffer_time, end_time__gt=start_dt - buffer_time, status__in=['APPROVED', 'PENDING']).exclude(id=booking.id).exists()
        if is_overlap: return JsonResponse({'status': 'error', 'message': 'เวลาชนกับรายการอื่น'}, status=400)

        booking.start_time = start_dt
        booking.end_time = end_dt
        
        booking.status = 'PENDING'
        booking.is_user_seen = False
        
        booking.save()
        send_booking_notification(booking, '', 'แจ้งเตือน: มีการย้ายเวลาการจอง 🕒')
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def delete_booking_api(request, booking_id):
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        if not booking.can_user_edit_or_cancel(request.user): return JsonResponse({'status': 'error'}, status=403)
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
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def mark_notification_read(request, booking_id):
    try:
        b = get_object_or_404(Booking, pk=booking_id)
        b.is_user_seen = True
        b.save()
        return JsonResponse({'status': 'success'})
    except: return JsonResponse({'status': 'error'}, status=400)

# --- REPORTS ---

def get_date_range_from_request(request):
    """ฟังก์ชันช่วยคำนวณวันเริ่มต้น-สิ้นสุด จาก Request"""
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    period = request.GET.get('period', 'monthly')
    today = timezone.now().date()
    
    report_title = ""
    start_date = today
    end_date = today # Default คือถึงวันนี้

    # กรณี 1: ผู้ใช้เลือกวันที่เอง (Custom Date)
    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            report_title = f"สถิติระหว่าง {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
            return start_date, end_date, report_title, 'custom'
        except ValueError:
            pass # ถ้าแปลงวันที่ไม่ได้ ให้ไปใช้ logic เดิม

    # กรณี 2: ใช้ปุ่มลัด (Daily/Weekly/Monthly)
    if period == 'daily': 
        start_date = today
        report_title = f"สถิติประจำวันที่ {today.strftime('%d/%m/%Y')}"
    elif period == 'weekly': 
        start_date = today - timedelta(days=7)
        report_title = "สถิติย้อนหลัง 7 วัน"
    else: # monthly หรืออื่นๆ
        start_date = today - timedelta(days=30)
        report_title = "สถิติย้อนหลัง 30 วัน"
    
    return start_date, end_date, report_title, period

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    # 1. คำนวณช่วงเวลา (ใช้ฟังก์ชันช่วยด้านบน)
    start_date, end_date, report_title, current_period = get_date_range_from_request(request)
    dept_filter = request.GET.get('department', '')

    # 2. ตัวเลขสรุป (Dashboard Boxes)
    try:
        val_total_rooms = Room.objects.count()
        val_total_users = User.objects.count()
        val_bookings_today = Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count()
        val_pending_bookings = Booking.objects.filter(status='PENDING').count()
    except:
        val_total_rooms = 0; val_total_users = 0; val_bookings_today = 0; val_pending_bookings = 0

    # 3. ดึงข้อมูลกราฟ (Query)
    # ใช้ __date__range เพื่อครอบคลุมทั้งวันเริ่มต้นและสิ้นสุด
    bookings_qs = Booking.objects.filter(
        start_time__date__range=[start_date, end_date], 
        status='APPROVED'
    )
    
    if dept_filter: 
        bookings_qs = bookings_qs.filter(department=dept_filter)

    # กราฟห้อง (Top 10)
    room_stats = bookings_qs.values('room__name').annotate(count=Count('id')).order_by('-count')[:10]
    room_labels = [item['room__name'] for item in room_stats]
    room_data = [item['count'] for item in room_stats]

    # กราฟแผนก (Top 10)
    dept_stats = bookings_qs.values('department').annotate(count=Count('id')).order_by('-count')[:10]
    dept_labels = [item['department'] for item in dept_stats if item['department']]
    dept_data = [item['count'] for item in dept_stats if item['department']]
    
    all_departments = Booking.objects.exclude(department__isnull=True).exclude(department__exact='').values_list('department', flat=True).distinct().order_by('department')

    context = get_base_context(request)
    context.update({
        'total_rooms': val_total_rooms,
        'total_users': val_total_users,
        'bookings_today': val_bookings_today,
        'pending_bookings': val_pending_bookings,
        'room_usage_labels': json.dumps(room_labels),
        'room_usage_data': json.dumps(room_data),
        'dept_usage_labels': json.dumps(dept_labels),
        'dept_usage_data': json.dumps(dept_data),
        'all_departments': all_departments,
        
        # ส่งค่ากลับไปหน้าเว็บเพื่อให้ Input คงค่าเดิมไว้
        'current_period': current_period,
        'current_department': dept_filter,
        'report_title': report_title,
        'start_date_val': start_date.strftime('%Y-%m-%d'),
        'end_date_val': end_date.strftime('%Y-%m-%d'),
    })

    return render(request, 'pages/reports.html', context)

# =========================================================================
# Export Excel
# =========================================================================
@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    start_date, end_date, _, _ = get_date_range_from_request(request)
    dept_filter = request.GET.get('department', '')

    bookings_qs = Booking.objects.filter(
        start_time__date__range=[start_date, end_date], 
        status='APPROVED'
    ).select_related('room', 'user').order_by('-start_time')
    
    if dept_filter: bookings_qs = bookings_qs.filter(department=dept_filter)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="report.csv"'
    
    # [สำคัญ] ใส่ BOM ให้ Excel อ่านภาษาไทยออก
    response.write(u'\ufeff'.encode('utf-8-sig'))
    
    writer = csv.writer(response)
    writer.writerow(['วันที่', 'เวลา', 'หัวข้อ', 'ห้อง', 'ผู้จอง', 'แผนก'])
    
    for b in bookings_qs:
        # [สำคัญ] แปลงเวลาจาก UTC เป็น Local Time (Bangkok)
        local_start = timezone.localtime(b.start_time)
        local_end = timezone.localtime(b.end_time)
        
        writer.writerow([
            local_start.strftime('%d/%m/%Y'), 
            f"{local_start.strftime('%H:%M')} - {local_end.strftime('%H:%M')}",
            b.title, 
            b.room.name, 
            b.user.get_full_name(), 
            b.department
        ])
    return response

# =========================================================================
# Export PDF - ใช้ xhtml2pdf + Embed Base64 Font (รองรับภาษาไทยชัวร์)
# =========================================================================
@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    start_date, end_date, title, _ = get_date_range_from_request(request)
    dept_filter = request.GET.get('department', '')

    bookings_qs = Booking.objects.filter(
        start_time__date__range=[start_date, end_date], 
        status='APPROVED'
    ).select_related('room', 'user').order_by('-start_time')
    
    if dept_filter: bookings_qs = bookings_qs.filter(department=dept_filter)
    
    # --- [ส่วนที่แก้ไข: อ่านไฟล์ Font และแปลงเป็น Base64] ---
    font_base64 = ""
    try:
        # พยายามหาไฟล์ฟอนต์
        font_path = finders.find('fonts/THSarabunNew.ttf')
        
        if not font_path:
             # กรณีหาไม่เจอ ให้ลองดูใน static โดยตรง
             font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'THSarabunNew.ttf')

        if font_path and os.path.exists(font_path):
            with open(font_path, "rb") as pdf_font_file:
                # อ่านไฟล์เป็น binary และแปลงเป็น base64 string
                encoded_string = base64.b64encode(pdf_font_file.read())
                font_base64 = encoded_string.decode("utf-8")
        else:
            print("⚠️ Warning: Font THSarabunNew.ttf not found in static/fonts/")

    except Exception as e:
        print(f"Font Error: {e}")

    # ส่งตัวแปร font_base64 ไปยัง template
    context = {
        'bookings': bookings_qs, 
        'export_date': timezone.now(), 
        'user': request.user, 
        'report_title': title,
        'font_base64': font_base64 
    }
    
    # ใช้ template reports_pdf.html ที่เตรียมไว้
    # แก้เป็น
    template = get_template('pages/reports_pdf.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    filename = f"report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # สร้าง PDF
    pisa_status = pisa.CreatePDF(html, dest=response, encoding='utf-8', link_callback=link_callback)

    if pisa_status.err:
       messages.error(request, "PDF Error")
       return redirect('reports')
    
    return response

@csrf_exempt
def teams_action_receiver(request): return HttpResponse(status=200)

@login_required
@require_POST
def mark_all_notifications_read(request):
    try:
        if is_admin(request.user):
            Booking.objects.filter(
                Q(status='PENDING') | Q(status='CANCELLED'),
                is_user_seen=False
            ).update(is_user_seen=True)
        else:
            Booking.objects.filter(user=request.user, is_user_seen=False).update(is_user_seen=True)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# -------------------------------------------------------------------------
# [NEW] AJAX Delete Room Image
# -------------------------------------------------------------------------
@login_required
@require_POST
def delete_room_image(request, room_id):
    """
    ฟังก์ชันสำหรับลบรูปภาพห้องผ่าน AJAX
    """
    try:
        room = get_object_or_404(Room, pk=room_id)
        
        # ตรวจสอบว่ามีรูปจริงไหม
        if room.image:
            # ลบไฟล์ออกจาก Storage (Optional: ถ้าอยากให้ลบไฟล์ขยะทิ้งด้วย)
            room.image.delete(save=False)
            
            # เคลียร์ค่าใน Database
            room.image = None
            room.save()
            
            return JsonResponse({'status': 'success', 'message': 'ลบรูปภาพเรียบร้อยแล้ว'})
        else:
            return JsonResponse({'status': 'error', 'message': 'ไม่พบรูปภาพ'}, status=400)
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)