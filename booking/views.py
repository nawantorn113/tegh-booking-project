import json
import re
import requests
from datetime import datetime, timedelta, time
import os
from collections import defaultdict
from dateutil.relativedelta import relativedelta

# Imports สำหรับ PDF และ Static Files
from weasyprint import HTML
from django.contrib.staticfiles.storage import staticfiles_storage

# Imports พื้นฐานของ Django
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

# LINE SDK Imports
try:
    from linebot import LineBotApi, WebhookHandler
    from linebot.models import TextSendMessage, MessageEvent, TextMessage
    from linebot.exceptions import InvalidSignatureError, LineBotApiError
except ImportError:
    LineBotApi = None
    WebhookHandler = None

# Import Models และ Forms
from .models import Room, Booking, AuditLog, OutlookToken, UserProfile
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm, CustomUserCreationForm
from .outlook_client import OutlookClient 

# Setup LINE Bot
line_bot_api = None
handler = None
if hasattr(settings, 'LINE_CHANNEL_ACCESS_TOKEN') and hasattr(settings, 'LINE_CHANNEL_SECRET'):
    try:
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
    except: pass
    
# ----------------------------------------------------------------------
# A. HELPER FUNCTIONS & CONTEXT 
# ----------------------------------------------------------------------

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists())

def is_approver_or_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=['Approver', 'Admin']).exists())

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_admin_emails(): 
    return list(User.objects.filter(Q(groups__name='Admin') | Q(is_superuser=True), is_active=True).distinct().exclude(email__exact='').values_list('email', flat=True))

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

# --- LINE Webhook & Notification Logic ---

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
            print(f"❌ Handler Error: {e}")
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
                msg = f"✅ ลงทะเบียนสำเร็จ!\nสวัสดีคุณ {user.get_full_name() or user.username}\nระบบจะแจ้งเตือนการจองมาที่นี่ครับ"
            except IndexError:
                msg = "⚠️ พิมพ์ผิดครับ\nพิมพ์: ลงทะเบียน [username]"
            except User.DoesNotExist:
                msg = f"❌ ไม่พบชื่อผู้ใช้ในระบบ"
            except Exception as e:
                msg = f"❌ Error: {e}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    try: AuditLog.objects.create(user=user, action='LOGIN', ip_address=get_client_ip(request), details=f"{user.username} logged in")
    except: pass

@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs): pass 

def send_booking_notification(booking, template_name, subject_prefix):
    """ ส่งแจ้งเตือน Email และ LINE """
    print(f"\n--- 🔔 Notification Trigger: {subject_prefix} ---")

    # 1. Email
    email_recipients = []
    if 'โปรดอนุมัติ' in subject_prefix:
        if booking.room.approver and booking.room.approver.email: email_recipients = [booking.room.approver.email]
        else: email_recipients = get_admin_emails()
    elif booking.user.email:
        email_recipients = [booking.user.email]
    
    if email_recipients:
        try:
            send_mail(f"[{subject_prefix}] {booking.title}", f"ห้อง: {booking.room.name}", settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=True)
        except: pass

    # 2. LINE OA
    line_targets = set() 
    
    # A. คนจอง
    try: 
        if booking.user.profile.line_user_id: line_targets.add(booking.user.profile.line_user_id)
    except: pass

    # B. ผู้อนุมัติ
    if 'โปรดอนุมัติ' in subject_prefix and booking.room.approver:
        try: 
            if booking.room.approver.profile.line_user_id: line_targets.add(booking.room.approver.profile.line_user_id)
        except: pass

    # C. ผู้เข้าร่วม
    if booking.participants.exists():
        for p in booking.participants.all():
            try:
                if p.profile.line_user_id: line_targets.add(p.profile.line_user_id)
            except: pass

    if line_targets and line_bot_api:
        # [NEW] เพิ่มข้อความแจ้งเตือนอุปกรณ์
        extra_msg = ""
        has_req = bool(booking.additional_requests and booking.additional_requests.strip())
        has_eq = booking.equipments.exists() if hasattr(booking, 'equipments') else False
        
        if has_req or has_eq:
            extra_msg = "\n⚠️ *มีการขออุปกรณ์เสริม*"

        msg = f"📢 {subject_prefix}{extra_msg}\nห้อง: {booking.room.name}\nเรื่อง: {booking.title}\nเวลา: {booking.start_time.strftime('%d/%m %H:%M')}"
        
        for uid in line_targets:
            if uid:
                try:
                    line_bot_api.push_message(uid, TextSendMessage(text=msg))
                except Exception as e:
                    print(f" ❌ LINE Error ({uid}): {e}")

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        if self.q: qs = qs.filter( Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q) | Q(email__icontains=self.q) )
        return qs[:15]
    def get_result_label(self, item): return f"{item.get_full_name() or item.username} ({item.email or 'No email'})"

# ----------------------------------------------------------------------
# B. AUTHENTICATION & CORE VIEWS 
# ----------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    context = {}
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid(): login(request, form.get_user()); return redirect('dashboard')
        else: messages.error(request, "Login Failed")
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

# ----------------------------------------------------------------------
# C. SMART SEARCH (แก้ไขให้ใช้งานได้จริง)
# ----------------------------------------------------------------------
def parse_search_query(text):
    """
    แยกคำค้นหา: หาตัวเลข (จำนวนคน) และ ข้อความ (ชื่อห้อง)
    เช่น "10 คน" -> capacity=10
    """
    text = text.strip()
    capacity = None
    keyword = text

    # ใช้ Regex หาตัวเลข (เช่น 10, 20)
    match = re.search(r'(\d+)', text)
    if match:
        capacity = int(match.group(1))
        # ลบตัวเลขออกจาก Keyword เพื่อเอาส่วนที่เหลือไปหาชื่อห้อง
        keyword = re.sub(r'\d+\s*(คน|ท่าน|seats?)?', '', text).strip()
    
    return keyword, capacity

@login_required
def smart_search_view(request):
    # 1. รับค่าจากช่องค้นหา (URL: ?q=...)
    query = request.GET.get('q', '').strip()
    
    # 2. เตรียม QuerySet เริ่มต้น (ห้องทั้งหมด)
    rooms = Room.objects.all()
    
    if query:
        # 3. แปลงคำค้นหา
        keyword, capacity = parse_search_query(query)

        # 4. กรองตามจำนวนคน (ถ้ามีตัวเลข)
        if capacity:
            rooms = rooms.filter(capacity__gte=capacity) # หาห้องที่จุคนได้เพียงพอ

        # 5. กรองตามชื่อห้อง (ถ้ามีตัวหนังสือเหลืออยู่)
        if keyword:
            rooms = rooms.filter(
                Q(name__icontains=keyword) | 
                Q(building__icontains=keyword) |
                Q(facilities__icontains=keyword)
            )

    # 6. ส่งผลลัพธ์ไปที่หน้าจอ
    context = get_base_context(request)
    context.update({
        'query': query,             
        'available_rooms': rooms,   
        'search_count': rooms.count()
    })
    
    return render(request, 'pages/search_results.html', context)

# ----------------------------------------------------------------------
# D. MAIN PAGES & BOOKING LOGIC
# ----------------------------------------------------------------------
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
        if r.is_currently_under_maintenance: r.status, r.status_class = 'ปิดปรับปรุง', 'bg-secondary text-white'
        else:
            cur = r.bookings.filter(start_time__lte=now, end_time__gt=now, status__in=['APPROVED','PENDING']).first()
            if cur: r.status, r.status_class = ('รออนุมัติ', 'bg-warning text-dark') if cur.status=='PENDING' else ('ไม่ว่าง', 'bg-danger text-white')
            else: r.status, r.status_class = 'ว่าง', 'bg-success text-white'
        buildings[r.building or "General"].append(r)
    
    ctx = get_base_context(request)
    ctx.update({'buildings': dict(buildings), 'total_rooms': all_rooms.count(), 'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count()})
    return render(request, 'pages/dashboard.html', ctx)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.room = room; booking.user = request.user
            
            # เช็คเงื่อนไขที่ต้องรออนุมัติ
            p_count = form.cleaned_data.get('participant_count', 0)
            req_text = form.cleaned_data.get('additional_requests', '')
            has_req = bool(req_text and req_text.strip()) 
            
            if p_count >= 15 or has_req: 
                booking.status = 'PENDING'
                msg = "รอการอนุมัติ (คนเยอะ/มีคำขอพิเศษ)"
            else: 
                booking.status = 'APPROVED'
                msg = "จองสำเร็จ"
            
            booking.save()
            form.save_m2m()
            
            if hasattr(booking, 'equipments') and booking.equipments.exists() and booking.status == 'APPROVED':
                booking.status = 'PENDING'; msg = "รอการอนุมัติ (อุปกรณ์)"; booking.save()

            messages.success(request, f"บันทึกสำเร็จ: {msg}")
            subj = 'โปรดอนุมัติ' if booking.status == 'PENDING' else 'จองสำเร็จ'
            send_booking_notification(booking, '', subj)
            return redirect('dashboard')
    else: form = BookingForm(initial={'room': room})
    ctx = get_base_context(request); ctx.update({'room': room, 'form': form})
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
    b = get_object_or_404(Booking, pk=booking_id)
    ctx = get_base_context(request)
    ctx.update({'booking': b, 'can_edit_or_cancel': b.can_user_edit_or_cancel(request.user) if request.user.is_authenticated else False, 'is_public_view': not request.user.is_authenticated})
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
            booking = form.save(commit=False)
            
            p_count = form.cleaned_data.get('participant_count', 0)
            req_text = form.cleaned_data.get('additional_requests', '')
            has_req = bool(req_text and req_text.strip())
            
            has_eq = False
            if 'equipments' in form.cleaned_data and hasattr(booking, 'equipments'):
                 if form.cleaned_data['equipments'].exists(): has_eq = True
            
            if p_count >= 15 or has_req or has_eq: 
                booking.status = 'PENDING'
                subj = 'โปรดอนุมัติ (แก้ไข)'
            else: 
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
    try: 
        s_dt = datetime.fromisoformat(start.replace('Z','+00:00'))
        e_dt = datetime.fromisoformat(end.replace('Z','+00:00'))
        qs = Booking.objects.filter(start_time__lt=e_dt, end_time__gt=s_dt, status__in=['APPROVED','PENDING'])
        events = []
        for b in qs:
            title = b.title
            
            has_req = bool(b.additional_requests and b.additional_requests.strip())
            has_eq = b.equipments.exists() if hasattr(b, 'equipments') else False
            if has_req or has_eq: title += " 🛠️"

            if not request.user.is_authenticated: title = "🔒 ไม่ว่าง" if b.status=='APPROVED' else "⏳ รออนุมัติ"
            events.append({'id': b.id, 'title': title, 'start': b.start_time.isoformat(), 'end': b.end_time.isoformat(), 'resourceId': b.room.id, 'extendedProps': {'status': b.status}})
        return JsonResponse(events, safe=False)
    except: return JsonResponse([], safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking = get_object_or_404(Booking, pk=data.get('booking_id'))
        if not (booking.user == request.user or is_admin(request.user)): return JsonResponse({'status': 'error', 'message': 'ไม่มีสิทธิ์แก้ไข'}, status=403)
        booking.start_time = datetime.fromisoformat(data.get('start_time').replace('Z', '+00:00'))
        booking.end_time = datetime.fromisoformat(data.get('end_time').replace('Z', '+00:00')) if data.get('end_time') else booking.start_time + timedelta(hours=1)
        booking.save()
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id): pass
@require_POST
def teams_action_receiver(request): pass
def _update_outlook_after_teams_action(booking): pass
def _update_teams_card_after_action(booking, new_status, action_type): pass

# ----------------------------------------------------------------------
# I. MANAGEMENT, REPORTS, EXPORT
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
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': RoomForm()})
@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    r = get_object_or_404(Room, pk=room_id)
    if request.method=='POST': form=RoomForm(request.POST, request.FILES, instance=r); form.save(); return redirect('rooms')
    return render(request, 'pages/room_form.html', {**get_base_context(request), 'form': RoomForm(instance=r)})
@login_required
@require_POST
def delete_room_view(request, room_id): Room.objects.filter(pk=room_id).delete(); return redirect('rooms')
@login_required
def audit_log_view(request): return render(request, 'pages/audit_log.html', {**get_base_context(request), 'page_obj': Paginator(AuditLog.objects.all().order_by('-timestamp'), 25).get_page(request.GET.get('page'))})

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    today = timezone.now().date(); start = today.replace(day=1)
    stats = Room.objects.annotate(booking_count=Count('bookings', filter=Q(bookings__start_time__date__gte=start, bookings__status__in=['APPROVED','PENDING']))).order_by('-booking_count')
    return render(request, 'pages/reports.html', {**get_base_context(request), 'room_usage_labels': json.dumps([r.name for r in stats]), 'room_usage_data': json.dumps([r.booking_count for r in stats])})

@login_required
@user_passes_test(is_admin)
def export_reports_excel(request): return HttpResponse("Excel Export")
@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request): 
    today = timezone.now().date(); start = today.replace(day=1)
    bookings = Booking.objects.filter(start_time__date__gte=start).order_by('start_time')
    ctx = {'bookings': bookings, 'report_title': f"Report {start}", 'export_date': timezone.now(), 'user': request.user}
    html = render_to_string('pages/reports_pdf.html', ctx)
    res = HttpResponse(content_type='application/pdf'); res['Content-Disposition'] = f'attachment; filename="report.pdf"'
    try: HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf(res); return res
    except: return redirect('reports')

def outlook_connect(request): pass
def outlook_callback(request): pass