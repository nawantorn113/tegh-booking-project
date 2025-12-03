import json
import re
import requests
import csv
import uuid # สำหรับการจองซ้ำ
from datetime import datetime, timedelta, time
import os
from collections import defaultdict
from dateutil.relativedelta import relativedelta # สำหรับการจองซ้ำรายเดือน

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.template.loader import get_template, render_to_string
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from dal_select2.views import Select2QuerySetView
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

# --- PDF Imports (WeasyPrint) ---
try:
    from weasyprint import HTML, CSS
except ImportError:
    HTML = None
    CSS = None

# --- LINE SDK ---
try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.models import TextSendMessage, MessageEvent, TextMessage
    from linebot.exceptions import InvalidSignatureError, LineBotApiError
except ImportError:
    LineBotApi = None
    WebhookHandler = None

from .models import Room, Booking, AuditLog, OutlookToken, UserProfile
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm, CustomUserCreationForm

# Setup LINE Bot
line_bot_api = None
handler = None
if hasattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN') and hasattr(settings, 'LINE_CHANNEL_SECRET'):
    try:
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
    except:
        pass

# ----------------------------------------------------------------------
# A. HELPER FUNCTIONS & CONTEXT
# ----------------------------------------------------------------------

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists())

def is_approver_or_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=['Approver', 'Admin']).exists())

def get_admin_emails():
    return list(User.objects.filter(Q(groups__name='Admin') | Q(is_superuser=True), is_active=True).distinct().exclude(email__exact='').values_list('email', flat=True))

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

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

    if request.user.is_authenticated and is_approver_or_admin(request.user):
        rooms_we_approve = Q(room__approver=request.user)
        rooms_for_central_admin = Q(room__approver__isnull=True)

        if is_admin(request.user):
            pending_query = rooms_we_approve | rooms_for_central_admin
        else:
            pending_query = rooms_we_approve

        pending_bookings = Booking.objects.filter(pending_query, status='PENDING').order_by('-created_at')
        pending_count = pending_bookings.count()
        pending_notifications = pending_bookings[:5]

    return {
        'menu_items': menu_items,
        'admin_menu_items': admin_menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,
        'pending_notifications': pending_notifications,
    }

# --- LINE Webhook ---
@csrf_exempt
def line_webhook(request):
    if request.method == 'POST':
        signature = request.META.get('HTTP_X_LINE_SIGNATURE', '')
        body = request.body.decode('utf-8')
        try:
            if handler: handler.handle(body, signature)
        except InvalidSignatureError:
            return HttpResponse(status=400)
        except Exception as e:
            print(f"Handler Error: {e}")
        return HttpResponse(status=200)
    return HttpResponse(status=405)

if handler:
    @handler.add(MessageEvent, message=TextMessage)
    def handle_message(event):
        text = event.message.text.strip()
        user_id = event.source.user_id
        if text.startswith("ลงทะเบียน"):
            try:
                username = text.split()[1]
                user = User.objects.get(username=username)
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.line_user_id = user_id
                profile.save()
                msg = f"ลงทะเบียนสำเร็จ! สวัสดีคุณ {user.get_full_name() or user.username}"
            except:
                msg = "พิมพ์ผิด หรือไม่พบ User"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

def send_booking_notification(booking, template_name, subject_prefix):
    """ ส่งแจ้งเตือน LINE และ Email หาแอดมินและผู้เกี่ยวข้อง """
    equip_text = "-"
    if hasattr(booking, 'equipments') and booking.equipments.exists():
        equip_names = [eq.name for eq in booking.equipments.all()]
        equip_text = ", ".join(equip_names)

    note_text = booking.additional_requests if booking.additional_requests else "-"
    start_str = booking.start_time.strftime('%d/%m/%Y %H:%M')
    end_str = booking.end_time.strftime('%H:%M')

    # LINE
    if line_bot_api:
        line_targets = set()
        try:
            if booking.user.profile.line_user_id: line_targets.add(booking.user.profile.line_user_id)
        except: pass
        if booking.room.approver:
            try:
                if booking.room.approver.profile.line_user_id: line_targets.add(booking.room.approver.profile.line_user_id)
            except: pass

        # ส่งหา Superuser ทุกคน
        admins = User.objects.filter(is_superuser=True)
        for admin in admins:
            try:
                if hasattr(admin, 'profile') and admin.profile.line_user_id: line_targets.add(admin.profile.line_user_id)
            except: pass

        msg = (f"{subject_prefix}\n-------------------------\n"
               f"ผู้จอง: {booking.user.get_full_name() or booking.user.username}\n"
               f"ห้อง: {booking.room.name}\n"
               f"เรื่อง: {booking.title}\n"
               f"เวลา: {start_str} - {end_str}\n"
               f"อุปกรณ์: {equip_text}\n"
               f"เพิ่มเติม: {note_text}\n"
               f"-------------------------\n"
               f"สถานะ: {booking.get_status_display()}")

        for uid in line_targets:
            if uid:
                try: line_bot_api.push_message(uid, TextSendMessage(text=msg))
                except: pass

    # Email
    email_recipients = []
    if 'โปรดอนุมัติ' in subject_prefix:
        if booking.room.approver and booking.room.approver.email: email_recipients = [booking.room.approver.email]
        else:
            email_recipients = get_admin_emails()
    elif booking.user.email:
        email_recipients = [booking.user.email]

    if email_recipients:
        try:
            send_mail(f"[{subject_prefix}] {booking.title}",
                      f"รายละเอียดการจอง:\n\nห้อง: {booking.room.name}\nอุปกรณ์: {equip_text}\nเพิ่มเติม: {note_text}",
                      settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=True)
        except: pass

# --- Views ---
class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        if self.q: qs = qs.filter( Q(username__icontains=self.q) | Q(first_name__icontains=self.q) )
        return qs[:15]

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid(): login(request, form.get_user()); return redirect('dashboard')
        else: messages.error(request, "เข้าสู่ระบบไม่สำเร็จ")
    else: form = AuthenticationForm()
    return render(request, 'login_card.html', {'form': form})

def sso_login_view(request): return redirect('login')

@login_required
def logout_view(request): logout(request); return redirect('login')

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid(): form.save(); update_session_auth_hash(request, request.user); return redirect('change_password')
    else: form = CustomPasswordChangeForm(request.user)
    return render(request, 'pages/change_password.html', {**get_base_context(request), 'password_form': form})

def public_calendar_view(request):
    ctx = get_base_context(request); ctx.update({'all_rooms': Room.objects.all(), 'is_public_view': True})
    return render(request, 'pages/master_calendar.html', ctx)

@login_required
def smart_search_view(request):
    query = request.GET.get('q', '').strip()
    rooms = Room.objects.all()
    if query:
        match = re.search(r'(\d+)', query)
        capacity = int(match.group(1)) if match else None
        keyword = re.sub(r'\d+\s*(คน|ท่าน|seats?)?', '', query).strip()
        if capacity: rooms = rooms.filter(capacity__gte=capacity)
        if keyword: rooms = rooms.filter(Q(name__icontains=keyword) | Q(building__icontains=keyword))
    context = get_base_context(request)
    context.update({'query': query, 'available_rooms': rooms, 'search_count': rooms.count()})
    return render(request, 'pages/search_results.html', context)

@login_required
def dashboard_view(request):
    now = timezone.now(); sort_by = request.GET.get('sort', 'floor')
    all_rooms = Room.objects.all()
    if sort_by == 'status':
        all_rooms_sorted = sorted(all_rooms, key=lambda r: (r.is_currently_under_maintenance, not r.bookings.filter(start_time__lte=now, end_time__gt=now, status__in=['APPROVED', 'PENDING']).exists()))
    elif sort_by == 'capacity': all_rooms_sorted = sorted(all_rooms, key=lambda r: r.capacity, reverse=True)
    elif sort_by == 'name': all_rooms_sorted = all_rooms.order_by('name')
    else: all_rooms_sorted = all_rooms.order_by('building', 'floor', 'name')

    buildings = defaultdict(list)
    for r in all_rooms_sorted:
        cur = r.bookings.filter(start_time__lte=now, end_time__gt=now, status__in=['APPROVED','PENDING']).first()
        if r.is_currently_under_maintenance:
            r.status, r.status_class = 'ปิดปรับปรุง', 'bg-secondary text-white'
            r.is_maintenance = True
            r.current_booking_info = None
        else:
            r.is_maintenance = False
            if cur:
                r.status, r.status_class = ('รออนุมัติ', 'bg-warning text-dark') if cur.status == 'PENDING' else ('ไม่ว่าง', 'bg-danger text-white')
                r.current_booking_info = cur
            else:
                r.status, r.status_class = 'ว่าง', 'bg-success text-white'
                r.current_booking_info = None
        buildings[r.building or "General"].append(r)

    summary_cards = {
        'total_rooms': all_rooms.count(),
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': Booking.objects.filter(status='PENDING').count(),
        'total_users_count': User.objects.count()
    }
    ctx = get_base_context(request)
    ctx.update({'buildings': dict(buildings), 'summary_cards': summary_cards, 'current_sort': sort_by})
    return render(request, 'pages/dashboard.html', ctx)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            # --- ส่วนจัดการการจองซ้ำ (Recurring Logic) ---
            recurrence = form.cleaned_data.get('recurrence')
            recurrence_end_date = form.cleaned_data.get('recurrence_end_date')
            
            base_booking = form.save(commit=False)
            base_booking.room = room
            base_booking.user = request.user
            
            duration = base_booking.end_time - base_booking.start_time
            
            current_start = base_booking.start_time
            current_end = base_booking.end_time
            bookings_to_create = []
            conflict_dates = []
            
            group_id = uuid.uuid4() if recurrence != 'NONE' else None
            
            if recurrence != 'NONE' and recurrence_end_date:
                loop_limit_date = recurrence_end_date
            else:
                loop_limit_date = current_start.date()

            # Loop ตรวจสอบและสร้างรายการจอง
            while current_start.date() <= loop_limit_date:
                is_overlap = Booking.objects.filter(
                    room=room,
                    start_time__lt=current_end,
                    end_time__gt=current_start,
                    status__in=['APPROVED', 'PENDING']
                ).exists()
                
                if is_overlap:
                    conflict_dates.append(current_start.strftime('%d/%m/%Y %H:%M'))
                
                bookings_to_create.append({
                    'start': current_start,
                    'end': current_end
                })
                
                # ขยับเวลาไปรอบถัดไป
                if recurrence == 'WEEKLY':
                    current_start += timedelta(weeks=1)
                elif recurrence == 'MONTHLY':
                    current_start += relativedelta(months=1)
                else:
                    break
                
                current_end = current_start + duration

            # --- ตรวจสอบผลลัพธ์ ---
            if conflict_dates:
                messages.error(request, f"จองไม่สำเร็จ! มีรายการซ้ำกับผู้อื่นในวันเวลา: {', '.join(conflict_dates)}")
                ctx = get_base_context(request)
                ctx.update({'room': room, 'form': form})
                return render(request, 'pages/room_calendar.html', ctx)
            
            else:
                # บันทึกข้อมูลจริง (Save)
                count = 0
                for info in bookings_to_create:
                    new_booking = Booking(
                        title=base_booking.title,
                        room=base_booking.room,
                        user=base_booking.user,
                        start_time=info['start'],
                        end_time=info['end'],
                        participant_count=base_booking.participant_count,
                        description=base_booking.description,
                        additional_requests=base_booking.additional_requests,
                        additional_notes=base_booking.additional_notes,
                        department=base_booking.department,
                        chairman=base_booking.chairman,
                        presentation_file=base_booking.presentation_file,
                    )
                    
                    has_req = bool(new_booking.additional_requests and new_booking.additional_requests.strip())
                    has_notes = bool(new_booking.additional_notes and new_booking.additional_notes.strip())
                    
                    if (new_booking.participant_count and new_booking.participant_count >= 15) or has_req or has_notes:
                        new_booking.status = 'PENDING'
                    else:
                        new_booking.status = 'APPROVED'
                    
                    new_booking.save()
                    
                    # จัดการ Many-to-Many (Participants, Equipments)
                    if 'participants' in form.cleaned_data:
                         new_booking.participants.set(form.cleaned_data['participants'])
                    if 'equipments' in form.cleaned_data:
                         new_booking.equipments.set(form.cleaned_data['equipments'])

                    # ส่งแจ้งเตือน (ส่งเฉพาะรายการแรก)
                    if count == 0: 
                         send_booking_notification(new_booking, '', ('โปรดอนุมัติ' if new_booking.status == 'PENDING' else 'จองสำเร็จ'))
                    
                    count += 1

                msg_success = f"จองสำเร็จ {count} รายการ" + (" (แบบต่อเนื่อง)" if count > 1 else "")
                messages.success(request, msg_success)
                return redirect('dashboard')
                
    else: 
        form = BookingForm(initial={'room': room})
    
    ctx = get_base_context(request)
    ctx.update({'room': room, 'form': form})
    return render(request, 'pages/room_calendar.html', ctx)

@login_required
def master_calendar_view(request):
    ctx = get_base_context(request); ctx['all_rooms'] = Room.objects.all()
    return render(request, 'pages/master_calendar.html', ctx)

@login_required
def history_view(request):
    qs = Booking.objects.all() if is_admin(request.user) else Booking.objects.filter(user=request.user)
    ctx = get_base_context(request); ctx.update({'bookings_list': qs.order_by('-start_time'), 'status_choices': Booking.STATUS_CHOICES})
    return render(request, 'pages/history.html', ctx)

def booking_detail_view(request, booking_id):
    try:
        b = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        messages.error(request, "ไม่พบข้อมูลการจองนี้ (อาจถูกลบไปแล้ว)")
        return redirect('history')

    ctx = get_base_context(request)
    can_edit = b.can_user_edit_or_cancel(request.user) if request.user.is_authenticated else False

    ctx.update({
        'booking': b,
        'can_edit_or_cancel': can_edit,
        'is_public_view': not request.user.is_authenticated
    })
    return render(request, 'pages/booking_detail.html', ctx)

# ----------------------------------------------------------------------
# E. APPROVALS & CRUD
# ----------------------------------------------------------------------
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    if is_admin(request.user): pending_query = Q(room__approver=request.user) | Q(room__approver__isnull=True)
    else: pending_query = Q(room__approver=request.user)
    pending_bookings = Booking.objects.filter(pending_query, status='PENDING').order_by('start_time')
    context = get_base_context(request); context.update({'pending_bookings': pending_bookings})
    return render(request, 'pages/approvals.html', context)

@login_required
def create_booking_view(request, room_id): return room_calendar_view(request, room_id)

@login_required
def edit_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    if not b.can_user_edit_or_cancel(request.user): messages.error(request, "ไม่มีสิทธิ์แก้ไข"); return redirect('history')
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=b)
        if form.is_valid():
            # NOTE: โค้ดนี้ไม่ได้รองรับการแก้ไขการจองซ้ำทั้งซีรีส์
            
            booking = form.save(commit=False)

            # --- Time Overlap Check (Exclude self) ---
            is_overlap = Booking.objects.filter(
                room=booking.room,
                start_time__lt=booking.end_time,
                end_time__gt=booking.start_time,
                status__in=['APPROVED', 'PENDING']
            ).exclude(pk=booking.id).exists()

            if is_overlap:
                messages.error(request, "แก้ไขไม่สำเร็จ: ช่วงเวลานี้มีการจองแล้ว")
                ctx = get_base_context(request)
                ctx.update({'form': form, 'booking': b})
                return render(request, 'pages/edit_booking.html', ctx)

            p_count = form.cleaned_data.get('participant_count', 0)
            req_text = form.cleaned_data.get('additional_requests', '')
            has_req = bool(req_text and req_text.strip())
            has_eq = False
            if 'equipments' in form.cleaned_data and hasattr(booking, 'equipments'):
                 if form.cleaned_data['equipments'].exists(): has_eq = True

            if (p_count and p_count >= 15) or has_req or has_eq:
                booking.status = 'PENDING'; subj = 'โปรดอนุมัติ (แก้ไข)'
            else:
                booking.status = 'APPROVED' if b.status == 'APPROVED' else 'PENDING'
                subj = 'แก้ไขการจอง'

            booking.save(); form.save_m2m(); messages.success(request, "แก้ไขเรียบร้อย")
            send_booking_notification(booking, '', subj)
            return redirect('history')
    else: form = BookingForm(instance=b)
    ctx = get_base_context(request); ctx.update({'form': form, 'booking': b})
    return render(request, 'pages/edit_booking.html', ctx)

@login_required
@require_POST
def delete_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id)
    if b.can_user_edit_or_cancel(request.user): b.status = 'CANCELLED'; b.save(); messages.success(request, "ยกเลิกสำเร็จ")
    return redirect('history')

@login_required
@require_POST
def approve_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id); b.status = 'APPROVED'; b.save()
    messages.success(request, "อนุมัติแล้ว"); send_booking_notification(b, '', 'อนุมัติแล้ว')
    return redirect('approvals')

@login_required
@require_POST
def reject_booking_view(request, booking_id):
    b = get_object_or_404(Booking, pk=booking_id); b.status = 'REJECTED'; b.save()
    messages.success(request, "ปฏิเสธแล้ว"); send_booking_notification(b, '', 'ถูกปฏิเสธ')
    return redirect('approvals')

# ----------------------------------------------------------------------
# F. APIS
# ----------------------------------------------------------------------
def rooms_api(request): return JsonResponse([{'id': r.id, 'title': r.name} for r in Room.objects.all()], safe=False)

def bookings_api(request):
    start = request.GET.get('start'); end = request.GET.get('end')
    room_id = request.GET.get('room_id')
    try:
        s_dt = datetime.fromisoformat(start.replace('Z','+00:00'))
        e_dt = datetime.fromisoformat(end.replace('Z','+00:00'))
        qs = Booking.objects.filter(start_time__lt=e_dt, end_time__gt=s_dt).exclude(status='CANCELLED').exclude(status='REJECTED')
        if room_id: qs = qs.filter(room_id=room_id)
        events = []
        for b in qs:
            title = b.title
            user_name = b.user.get_full_name() if b.user and b.user.get_full_name() else (b.user.username if b.user else "ไม่ระบุ")
            events.append({
                'id': b.id,
                'title': title,
                'start': b.start_time.isoformat(),
                'end': b.end_time.isoformat(),
                'resourceId': b.room.id,
                'extendedProps': {
                    'status': b.status,
                    'user': user_name,
                    'room': b.room.name,
                    'desc': b.additional_requests or "-"
                }
            })
        return JsonResponse(events, safe=False)
    except: return JsonResponse([], safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, pk=data.get('id'))

        # --- [FINAL SECURITY CHECK: Only Owner OR System Admin] ---
        is_owner = booking.user == request.user
        is_system_admin = is_admin(request.user)
        
        # ถ้าไม่ใช่เจ้าของ AND ไม่ใช่ System Admin -> ไม่อนุญาต
        if not (is_owner or is_system_admin):
            return JsonResponse({'status': 'error', 'message': 'ไม่มีสิทธิ์แก้ไข/ลากวางการจองนี้'}, status=403)
        # --- [END: Drag & Drop Permission Check] ---
        
        start_dt = datetime.fromisoformat(data.get('start').replace('Z', ''))
        end_str = data.get('end')

        if end_str:
            end_dt = datetime.fromisoformat(end_str.replace('Z', ''))
        else:
            duration = booking.end_time - booking.start_time
            end_dt = start_dt + duration

        # Check Overlap for Drag & Drop
        is_overlap = Booking.objects.filter(
            room=booking.room,
            start_time__lt=end_dt,
            end_time__gt=start_dt,
            status__in=['APPROVED', 'PENDING']
        ).exclude(pk=booking.id).exists()

        if is_overlap:
             return JsonResponse({'status': 'error', 'message': 'ช่วงเวลาซ้อนทับกับการจองอื่น'}, status=400)

        booking.start_time = start_dt
        booking.end_time = end_dt
        booking.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def api_pending_count(request):
    count = 0
    latest_booking = None

    if is_approver_or_admin(request.user):
        rooms_we_approve = Q(room__approver=request.user)
        rooms_for_central_admin = Q(room__approver__isnull=True)

        if is_admin(request.user):
            base_query = rooms_we_approve | rooms_for_central_admin
        else:
            base_query = rooms_we_approve

        count = Booking.objects.filter(base_query, status='PENDING').count()

        last_10_sec = timezone.now() - timedelta(seconds=10)
        new_b = Booking.objects.filter(created_at__gte=last_10_sec).order_by('-created_at').first()

        if new_b:
            eq_list = [e.name for e in new_b.equipments.all()]
            eq_str = ", ".join(eq_list) if eq_list else "ไม่มี"
            latest_booking = {
                'id': new_b.id,
                'user': new_b.user.get_full_name() or new_b.user.username,
                'room': new_b.room.name,
                'status': new_b.get_status_display(),
                'equipments': eq_str,
                'notes': new_b.additional_requests or "-"
            }

    return JsonResponse({'count': count, 'latest_booking': latest_booking})

@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id): pass
@require_POST
def teams_action_receiver(request): pass

# ----------------------------------------------------------------------
# G. ROOM MANAGEMENT & REPORTS
# ----------------------------------------------------------------------
@login_required
@user_passes_test(is_admin)
def user_management_view(request): return render(request, 'pages/user_management.html', {**get_base_context(request), 'users': User.objects.all()})

@login_required
@user_passes_test(is_admin)
def add_user_view(request):
    if request.method=='POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid(): form.save(); messages.success(request, "เพิ่มผู้ใช้แล้ว"); return redirect('user_management')
    else: form = CustomUserCreationForm()
    return render(request, 'pages/user_form.html', {**get_base_context(request), 'form': form, 'title': 'เพิ่มผู้ใช้'})

@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    if request.method=='POST':
        u.groups.set(Group.objects.filter(pk__in=request.POST.getlist('groups')))
        u.is_staff = u.groups.filter(name='Admin').exists(); u.is_superuser = u.is_staff; u.save()
        return redirect('user_management')
    return render(request, 'pages/edit_user_roles.html', {**get_base_context(request), 'user_to_edit': u, 'all_groups': Group.objects.all(), 'user_group_pks': list(u.groups.values_list('pk', flat=True))})

@login_required
@user_passes_test(is_admin)
def room_management_view(request): return render(request, 'pages/rooms.html', {**get_base_context(request), 'rooms': Room.objects.all()})

@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method=='POST': form=RoomForm(request.POST, request.FILES); form.save(); return redirect('rooms')
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form, 'title': 'เพิ่มห้อง'})

@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    r = get_object_or_404(Room, pk=room_id)
    if request.method=='POST': form=RoomForm(request.POST, request.FILES, instance=r); form.save(); return redirect('rooms')
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': form, 'title': 'แก้ไขห้อง'})

@login_required
@require_POST
def delete_room_view(request, room_id): Room.objects.filter(pk=room_id).delete(); return redirect('rooms')

@login_required
def audit_log_view(request): return render(request, 'pages/audit_log.html', {**get_base_context(request), 'page_obj': Paginator(AuditLog.objects.all().order_by('-timestamp'), 25).get_page(request.GET.get('page'))})

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
        report_title = f"สถิติย้อนหลัง 7 วัน ({start_date.strftime('%d/%m')} - {today.strftime('%d/%m/%Y')})"
    else:
        start_date = today - timedelta(days=30)
        report_title = f"สถิติย้อนหลัง 30 วัน ({start_date.strftime('%d/%m')} - {today.strftime('%d/%m/%Y')})"

    bookings_qs = Booking.objects.filter(start_time__date__gte=start_date, status='APPROVED')
    if dept_filter:
        try: bookings_qs = bookings_qs.filter(department=dept_filter)
        except: pass

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
    except: pass

    total_rooms = Room.objects.count()
    today_bookings = Booking.objects.filter(start_time__date=today, status='APPROVED').count()
    pending_approvals = Booking.objects.filter(status='PENDING').count()
    total_users = User.objects.count()

    context = get_base_context(request)
    context.update({
        'total_rooms_count': total_rooms, 'today_bookings_count': today_bookings, 'pending_count': pending_approvals, 'total_users_count': total_users,
        'room_usage_labels': json.dumps(room_labels), 'room_usage_data': json.dumps(room_data),
        'dept_usage_labels': json.dumps(dept_labels), 'dept_usage_data': json.dumps(dept_data),
        'all_departments': all_departments, 'current_period': period, 'current_department': dept_filter, 'report_title': report_title,
        'stats': Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__start_time__date__gte=start_date, bookings__status='APPROVED'))).order_by('-booking_count'),
        'report_month': today.strftime('%B %Y')
    })
    return render(request, 'pages/reports.html', context)

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    """
    ฟังก์ชันสำหรับ Export รายงานการจองเป็นไฟล์ CSV (เปิดใน Excel ได้)
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="booking_report.csv"'

    # เขียน BOM (Byte Order Mark) เพื่อให้ Excel อ่านภาษาไทยออก
    response.write(u'\ufeff'.encode('utf8'))

    writer = csv.writer(response)
    # เขียนหัวตาราง
    writer.writerow(['วันที่', 'เวลาเริ่ม', 'เวลาสิ้นสุด', 'หัวข้อ', 'ห้อง', 'ผู้จอง', 'สถานะ'])

    # ดึงข้อมูลการจองทั้งหมด (หรือจะกรองตามเดือนก็ได้ถ้าต้องการ)
    bookings = Booking.objects.all().order_by('-start_time')

    for b in bookings:
        writer.writerow([
            b.start_time.strftime('%d/%m/%Y'),
            b.start_time.strftime('%H:%M'),
            b.end_time.strftime('%H:%M'),
            b.title,
            b.room.name,
            b.user.get_full_name() if b.user else 'Unknown',
            b.get_status_display()
        ])
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    """
    ฟังก์ชันสำหรับ Export รายงานการจองเป็นไฟล์ PDF โดยใช้ WeasyPrint
    """
    # 1. ตรวจสอบ WeasyPrint
    if HTML is None:
        messages.error(request, "ไม่สามารถสร้าง PDF ได้: กรุณาติดตั้งไลบรารี WeasyPrint และ GTK3 runtime")
        return redirect('reports')

    # กรองข้อมูลการจอง (ดึงเฉพาะที่ อนุมัติ หรือ รออนุมัติ)
    bookings = Booking.objects.filter(status__in=['APPROVED', 'PENDING']).order_by('-start_time')

    # 2. เตรียม Context สำหรับ Template
    context = {
        'bookings': bookings,
        'report_title': 'รายงานการจองห้องประชุม',
        'export_date': timezone.now(),
        'user': request.user,
    }

    # 3. Render Template เป็น HTML String
    # ใช้ path 'pages/reports_pdf.html' ตามที่แก้ไขล่าสุด
    html_string = render_to_string('pages/reports_pdf.html', context)

    # 4. สร้าง PDF
    try:
        pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

        # 5. ส่งไฟล์ PDF เป็น Response
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="booking_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        return response

    except Exception as e:
        messages.error(request, f"เกิดข้อผิดพลาดในการสร้าง PDF: {e}")
        return redirect('reports')