import json
import re
import requests
from datetime import datetime, timedelta, time
import os 

# 💡 [ใหม่] Imports สำหรับ WeasyPrint (แทนที่ xhtml2pdf)
from weasyprint import HTML
from django.contrib.staticfiles.storage import staticfiles_storage

# ❌ ลบ Imports ของ xhtml2pdf (pisa) และ Pyppeteer ออกไปแล้ว

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from django.template.loader import get_template, render_to_string # 💡 ยังคงต้องใช้
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
from dateutil.relativedelta import relativedelta 

from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import Room, Booking, AuditLog, OutlookToken 
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm
from .outlook_client import OutlookClient 
    
from collections import defaultdict

# --- Helper Functions ---
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

# ✅✅✅ [FIX] get_base_context อยู่ที่นี่แล้ว ✅✅✅
# --- Context Function (สำหรับ Navbar) ---
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
    else:
        pending_bookings = Booking.objects.none() 

    return {
        'menu_items': menu_items,
        'admin_menu_items': admin_menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,
        'pending_notifications': pending_notifications,
        'pending_bookings': pending_bookings 
    }

# --- Callbacks / Email / Autocomplete / Outlook Helpers ---
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip_address = get_client_ip(request)
    try:
        AuditLog.objects.create(
            user=user, action='LOGIN', ip_address=ip_address,
            details=f"User {user.username} logged in."
        )
    except Exception as e:
        print(f"Failed to log LOGIN action for {user.username}: {e}")
    if is_admin(user):
        admin_emails = get_admin_emails()
        subject = f"[แจ้งเตือนความปลอดภัย] Admin/Superuser ล็อกอิน ({user.username})"
        message = (
            f"ผู้ใช้ Admin: {user.get_full_name() or user.username} เพิ่งเข้าสู่ระบบ\n"
            f"เวลา: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"จาก IP Address: {ip_address}"
        )
        try:
            send_mail(
                subject, message, settings.DEFAULT_FROM_EMAIL,
                admin_emails, fail_silently=True 
            )
            print(f"Security alert sent for admin login: {user.username}")
        except Exception as e:
            print(f"Error sending login security email: {e}")
@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    pass 
def get_admin_emails(): 
    return list(User.objects.filter(Q(groups__name='Admin') | Q(is_superuser=True), is_active=True).distinct().exclude(email__exact='').values_list('email', flat=True))
def send_booking_notification(booking, template_name, subject_prefix):
    recipients = []
    if 'โปรดอนุมัติ' in subject_prefix or 'จองสำเร็จ' in subject_prefix:
        if booking.room.approver and booking.room.approver.email:
            recipients = [booking.room.approver.email]
        else:
            recipients = get_admin_emails()
    elif booking.user and booking.user.email:
        recipients = [booking.user.email]
    if not recipients: 
        print(f"Skipping email '{subject_prefix}': No recipients found.")
    else:
        if not isinstance(recipients, list): recipients = [recipients]
        subject = f"[{subject_prefix}] การจองห้อง: {booking.title} ({booking.room.name})"
        context = {'booking': booking, 'settings': settings}
        try:
            message_html = render_to_string(template_name, context)
            if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
                send_mail(subject, message_html, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=message_html)
                print(f"Email '{subject}' sent to: {', '.join(recipients)}")
            else:
                send_mail(subject, "Fallback text", settings.DEFAULT_FROM_EMAIL, recipients, html_message=message_html)
        except Exception as e: 
            print(f"Error preparing/sending email '{subject}': {e}")
    line_token = booking.room.line_notify_token
    if line_token:
        try:
            line_url = 'https://notify-api.line.me/api/notify'
            headers = {'Authorization': f'Bearer {line_token}'}
            line_message = (
                f"\n🔔 {subject_prefix}\n"
                f"--------------------\n"
                f"ห้อง: {booking.room.name}\n"
                f"หัวข้อ: {booking.title}\n"
                f"ผู้จอง: {booking.user.get_full_name() or booking.user.username}\n"
                f"เวลา: {booking.start_time.strftime('%d/%m/%Y %H:%M')} - {booking.end_time.strftime('%H:%M')}"
            )
            payload = {'message': line_message}
            requests.post(line_url, headers=headers, data=payload, timeout=5)
            print(f"LINE Notify sent for Booking ID {booking.id}")
        except Exception as e:
            print(f"Error sending LINE Notify for Booking ID {booking.id}: {e}")
    teams_url = booking.room.teams_webhook_url
    if teams_url:
        try:
            is_pending = booking.status == 'PENDING'
            card_actions = []
            if is_pending:
                base_url = settings.AZURE_REDIRECT_URI.replace('/outlook/callback/', '')
                action_url = f"{base_url}{reverse('teams_action_receiver')}"
                card_actions.append({
                    "type": "Action.Http", "title": "✅ อนุมัติ", "method": "POST",
                    "url": action_url, "body": json.dumps({"bookingId": booking.id, "action": "approve"}), "style": "positive"
                })
                card_actions.append({
                    "type": "Action.Http", "title": "❌ ปฏิเสธ", "method": "POST",
                    "url": action_url, "body": json.dumps({"bookingId": booking.id, "action": "reject"}), "style": "destructive"
                })
            adaptive_card = {
                "type": "message", "attachments": [
                    {"contentType": "application/vnd.microsoft.card.adaptive", "content": {
                            "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.4",
                            "msteams": {"width": "Full"},
                            "body": [
                                {"type": "TextBlock", "text": f"🔔 {subject_prefix}", "weight": "Bolder", "size": "Medium",
                                 "color": "Warning" if is_pending else ("Attention" if "ถูกปฏิเสธ" in subject_prefix else "Good")},
                                {"type": "TextBlock", "text": f"รายละเอียดการจองห้อง: {booking.room.name}", "wrap": True, "spacing": "None"},
                                {"type": "FactSet", "spacing": "Large", "facts": [
                                        {"title": "หัวข้อ:", "value": booking.title},
                                        {"title": "ผู้จอง:", "value": f"{booking.user.get_full_name() or booking.user.username}"},
                                        {"title": "เวลาเริ่ม:", "value": f"{{{{DATE({booking.start_time.isoformat()})}}}} {{{{TIME({booking.start_time.isoformat()})}}}}"},
                                        {"title": "เวลาสิ้นสุด:", "value": f"{{{{DATE({booking.end_time.isoformat()})}}}} {{{{TIME({booking.end_time.isoformat()})}}}}"}
                                ]}
                            ], "actions": card_actions
                    }}
                ]
            }
            headers = {'Content-Type': 'application/json'}
            requests.post(teams_url, data=json.dumps(adaptive_card), headers=headers, timeout=5)
            print(f"Teams Webhook sent for Booking ID {booking.id}")
        except Exception as e:
            print(f"Error sending Teams Webhook for Booking ID {booking.id}: {e}")

class UserAutocomplete(Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated: return User.objects.none()
        qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        if self.q: qs = qs.filter( Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q) | Q(email__icontains=self.q) )
        return qs[:15]
    def get_result_label(self, item): return f"{item.get_full_name() or item.username} ({item.email or 'No email'})"

# --- Auth Views ---
def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST);
        if form.is_valid():
            user = form.get_user(); login(request, user)
            next_url = request.GET.get('next', 'dashboard'); messages.success(request, f"ยินดีต้อนรับ, {user.get_full_name() or user.username}!")
            return redirect(next_url)
        else:
            if '__all__' in form.errors: messages.error(request, f"ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้ง")
            else: messages.error(request, f"ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้ง")
    else: form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, f"คุณได้ออกจากระบบเรียบร้อยแล้ว");
    return redirect('login') 

# --- Smart Search ---
def parse_search_query(query_text):
    from datetime import datetime, time, timedelta 
    capacity = None
    start_time = None
    end_time = None
    now = timezone.now()
    today = now.date()
    capacity_match = re.search(r'(\d+)\s*คน', query_text)
    if capacity_match:
        capacity = int(capacity_match.group(1))
    if "บ่ายนี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, time(13, 0))) 
        end_time = timezone.make_aware(datetime.combine(today, time(17, 0)))
        if now > end_time: start_time, end_time = None, None 
    elif "เช้านี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, time(12, 0)))
        if now > end_time: start_time, end_time = None, None
    elif "พรุ่งนี้เช้า" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, time(12, 0)))
    elif "พรุ่งนี้บ่าย" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, time(13, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, time(17, 0)))
    elif "พรุ่งนี้" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, time(17, 0)))
    elif "วันนี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, time(17, 0)))
        if now > end_time: start_time, end_time = None, None
    return capacity, start_time, end_time
@login_required
def smart_search_view(request):
    query_text = request.GET.get('q', '')
    available_rooms = Room.objects.all().order_by('capacity') 
    valid_rooms = []
    search_params = {}
    capacity, start_time, end_time = None, None, None
    if query_text:
        capacity, start_time, end_time = parse_search_query(query_text)
        search_params['capacity'] = capacity
        search_params['start_time'] = start_time
        search_params['end_time'] = end_time
        rooms_to_check = available_rooms
        if capacity:
            rooms_to_check = rooms_to_check.filter(capacity__gte=capacity)
        for room in rooms_to_check:
            if room.is_currently_under_maintenance:
                continue
            if start_time and end_time:
                conflicts = Booking.objects.filter(
                    room=room, status__in=['APPROVED', 'PENDING'],
                    start_time__lt=end_time, end_time__gt=start_time
                ).exists()
                if not conflicts:
                    valid_rooms.append(room)
            elif not start_time and not end_time:
                valid_rooms.append(room)
    context = get_base_context(request)
    context.update({
        'query_text': query_text,
        'search_params': search_params,
        'available_rooms': valid_rooms, 
    })
    return render(request, 'pages/search_results.html', context)

# --- Main Pages ---
@login_required
def dashboard_view(request):
    now = timezone.now(); sort_by = request.GET.get('sort', 'floor')
    all_rooms = Room.objects.all()
    if sort_by == 'status':
        all_rooms_sorted = sorted(all_rooms, key=lambda r: (r.is_currently_under_maintenance, not r.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').exists()))
    elif sort_by == 'capacity':
        all_rooms_sorted = sorted(all_rooms, key=lambda r: r.capacity, reverse=True)
    elif sort_by == 'name':
        all_rooms_sorted = all_rooms.order_by('name')
    else: 
        all_rooms_sorted = all_rooms.order_by('building', 'floor', 'name')
    buildings = defaultdict(list)
    for room in all_rooms_sorted:
        if room.is_currently_under_maintenance: 
            room.status = 'ปิดปรับปรุง'
            room.status_class = 'status-maintenance' # 👈
            room.current_booking_info = None
            room.next_booking_info = None
        else:
            current = room.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').select_related('user').first()
            if current:
                room.status = 'ไม่ว่าง'
                room.status_class = 'status-occupied' # 👈
            else:
                room.status = 'ว่าง'
                room.status_class = 'status-available' # 👈
            room.current_booking_info = current
            room.next_booking_info = None
            if not current:
                room.next_booking_info = room.bookings.filter(start_time__gt=now, status='APPROVED').select_related('user').order_by('start_time').first()
        buildings[room.building or "(ไม่ได้ระบุอาคาร)"].append(room)
    my_bookings_today_count = Booking.objects.filter(user=request.user, start_time__date=now.date()).count()
    context = get_base_context(request)
    summary = {
        'total_rooms': all_rooms.count(), 
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': context['pending_count'], 
        'total_users_count': User.objects.count(), 
    }
    outlook_connected = OutlookToken.objects.filter(user__is_superuser=True).exists() if is_admin(request.user) else False
    context.update({
        'buildings': dict(buildings), 
        'summary_cards': summary, 
        'current_sort': sort_by, 
        'all_rooms': all_rooms_sorted,
        'outlook_connected': outlook_connected,
    })
    return render(request, 'pages/dashboard.html', context)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if room.is_currently_under_maintenance and not is_admin(request.user):
        messages.error(request, f"ห้อง '{room.name}' กำลังปิดปรับปรุงชั่วคราว ไม่สามารถเข้าดูปฏิทินได้")
        return redirect('dashboard')
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES) 
    else:
        form = BookingForm(initial={'room': room}) 
    context = get_base_context(request)
    context.update({
        'room': room, 
        'form': form,
        'current_user_id': request.user.id,
        'current_user_is_admin': is_admin(request.user)
    })
    return render(request, 'pages/room_calendar.html', context)

@login_required
def master_calendar_view(request):
    all_rooms = Room.objects.all().exclude(is_maintenance=True).order_by('building', 'floor', 'name')
    context = get_base_context(request)
    context.update({
        'all_rooms': all_rooms 
    })
    return render(request, 'pages/master_calendar.html', context)

@login_required
def history_view(request): 
    if is_admin(request.user):
        bookings = Booking.objects.all().select_related('room', 'user').order_by('-start_time')
    else:
        bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-start_time')
    date_f = request.GET.get('date'); room_f = request.GET.get('room'); status_f = request.GET.get('status'); q_f = request.GET.get('q', '')
    if date_f:
        try:
            bookings = bookings.filter(start_time__date=datetime.strptime(date_f, '%Y-%m-%d').date())
        except ValueError:
            messages.warning(request, f"รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD")
            date_f = None
    if room_f:
        try:
            room_id_int = int(room_f)
            bookings = bookings.filter(room_id=room_id_int)
        except (ValueError, TypeError):
            messages.warning(request, f"Room ID ไม่ถูกต้อง")
            room_f = None
    if status_f and status_f in dict(Booking.STATUS_CHOICES):
        bookings = bookings.filter(status=status_f)
    elif status_f:
        messages.warning(request, f"สถานะการจองไม่ถูกต้อง")
        status_f = None
    if q_f:
        bookings = bookings.filter(
            Q(title__icontains=q_f) |
            Q(user__username__icontains=q_f) |
            Q(user__first_name__icontains=q_f) |
            Q(user__last_name__icontains=q_f) |
            Q(department__icontains=q_f) |
            Q(participants__username__icontains=q_f) |
            Q(participants__first_name__icontains=q_f) |
            Q(participants__last_name__icontains=q_f)
        ).distinct()
    context = get_base_context(request)
    context.update({
        'bookings_list': bookings, 
        'all_rooms': Room.objects.all().order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
        'current_date': date_f,
        'current_room': room_f,
        'current_status': status_f,
        'current_query': q_f,
        'now_time': timezone.now()
    })
    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('room', 'user')
                            .prefetch_related('participants'), 
        pk=booking_id
    )
    context = get_base_context(request)
    context.update({
        'booking': booking,
        'can_edit_or_cancel': booking.can_user_edit_or_cancel(request.user)
    })
    return render(request, 'pages/booking_detail.html', context)

@login_required
def change_password_view(request): 
    if request.method == 'POST':
        password_form = CustomPasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, f"เปลี่ยนรหัสผ่านเรียบร้อยแล้ว");
            return redirect('change_password')
        else:
            messages.error(request, f"ไม่สามารถเปลี่ยนรหัสผ่านได้ กรุณาตรวจสอบข้อผิดพลาด")
    else: 
        password_form = CustomPasswordChangeForm(request.user)
    context = get_base_context(request)
    context.update({'password_form': password_form})
    return render(request, 'pages/change_password.html', context)

# ✅✅✅ [FIX] โค้ด Outlook ทั้งหมดอยู่ที่นี่แล้ว ✅✅✅
# ----------------------------------------------------
# 💡 [ใหม่] OUTLOOK CALENDAR INTEGRATION LOGIC (Helper)
# ----------------------------------------------------
def _get_valid_outlook_token():
    """
    ดึง Access Token ที่ใช้งานได้จาก Admin/Superuser คนแรก
    และทำการ Refresh Token หาก Access Token หมดอายุ
    """
    try:
        token_obj = OutlookToken.objects.filter(user__is_superuser=True).order_by('id').first()

        if not token_obj:
            return None

        # 1. ตรวจสอบว่า Access Token หมดอายุแล้วหรือไม่ (เหลือเวลาอีก 5 นาที)
        if token_obj.expires_at <= timezone.now() + timedelta(minutes=5):
            print("⏳ Outlook: Access Token หมดอายุหรือใกล้หมดอายุ กำลัง Refresh Token...")
            
            client = OutlookClient(settings.AZURE_REDIRECT_URI)
            refresh_token_data = client.refresh_token(token_obj.refresh_token)
            
            # อัปเดต Token ใน Database
            expires_in_seconds = refresh_token_data.get('expires_in', 3600)
            token_obj.access_token = refresh_token_data['access_token']
            token_obj.refresh_token = refresh_token_data.get('refresh_token', token_obj.refresh_token) 
            token_obj.expires_at = timezone.now() + timedelta(seconds=expires_in_seconds)
            token_obj.save()
            
            print("✅ Outlook: Refresh Token สำเร็จ")
            return token_obj.access_token

        # 2. Access Token ยังใช้งานได้
        return token_obj.access_token

    except requests.exceptions.HTTPError as e:
        print(f"❌ Outlook Refresh Error: {e.response.json()}")
        return None
    except Exception as e:
        print(f"❌ Outlook Token Error: {e}")
        return None
        
@login_required
@user_passes_test(is_admin)
def outlook_connect(request):
    """
    ขั้นตอนที่ 1: เริ่มต้นกระบวนการ OAuth โดยส่งผู้ใช้ไปที่ Microsoft
    """
    redirect_uri = settings.AZURE_REDIRECT_URI
    client = OutlookClient(redirect_uri)
    auth_url = client.get_auth_url()
    return redirect(auth_url)


@login_required
@user_passes_test(is_admin)
def outlook_callback(request):
    """
    ขั้นตอนที่ 2: รับ Authorization Code จาก Microsoft และแลกเป็น Token
    """
    code = request.GET.get('code')
    
    if not code:
        messages.error(request, "การเชื่อมต่อ Outlook ล้มเหลว: ไม่ได้รับรหัสยืนยัน (Authorization Code)")
        return redirect('dashboard')
    
    try:
        redirect_uri = settings.AZURE_REDIRECT_URI
        client = OutlookClient(redirect_uri)
        
        # 1. แลก Authorization Code เป็น Token
        token_data = client.get_token_from_code(code)
        
        # 2. คำนวณวันหมดอายุของ Access Token
        expires_in_seconds = token_data.get('expires_in', 3600)
        expires_at = timezone.now() + timedelta(seconds=expires_in_seconds)
        
        # 3. บันทึก/อัปเดต Token ลงใน Database
        OutlookToken.objects.update_or_create(
            user=request.user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', ''),
                'expires_at': expires_at,
            }
        )
        
        messages.success(request, "เชื่อมต่อปฏิทิน Outlook สำเร็จแล้ว!")
        
    except requests.exceptions.HTTPError as e:
        error_info = e.response.json()
        messages.error(request, f"การเชื่อมต่อ Outlook ล้มเหลว (Microsoft Error): {error_info.get('error_description', 'Unknown Error')}")
    except Exception as e:
        messages.error(request, f"เกิดข้อผิดพลาดในการประมวลผล Token: {e}")
        
    return redirect('dashboard') 

# --- APIs ---
@login_required
def rooms_api(request):
    rooms = Room.objects.all().exclude(is_maintenance=True).order_by('building', 'name')
    resources = [{
        'id': r.id, 
        'title': r.name, 
        'building': r.building or "",
        'capacity': r.capacity, 
        'floor': r.floor or ""
    } for r in rooms]
    return JsonResponse(resources, safe=False)

@login_required
def bookings_api(request):
    start_str = request.GET.get('start'); end_str = request.GET.get('end'); room_id = request.GET.get('room_id')
    if not start_str or not end_str: return JsonResponse({'error': 'Missing required start/end parameters.'}, status=400)
    try:
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace(' ', '+'))
        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00').replace(' ', '+'))
    except (ValueError, TypeError) as e: 
        print(f"Error parsing date: {e}")
        return JsonResponse({'error': f'Invalid date format: {start_str}'}, status=400)
    bookings = Booking.objects.filter(
        start_time__lt=end_dt, 
        end_time__gt=start_dt, 
        status__in=['APPROVED', 'PENDING']
    ).select_related('room', 'user').prefetch_related('participants')
    if room_id:
        try: bookings = bookings.filter(room_id=int(room_id))
        except (ValueError, TypeError): return JsonResponse({'error': f"Invalid room ID."})
    events = []
    for b in bookings:
        participants_data = []
        for p in b.participants.all():
            participants_data.append({
                'id': p.id,
                'text': p.get_full_name() or p.username 
            })
        events.append({
            'id': b.id, 
            'title': b.title, 
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(), 
            'resourceId': b.room.id,
            'extendedProps': { 
                'status': b.status, 
                'user_id': b.user.id if b.user else None,
                'chairman': b.chairman or "",
                'department': b.department or "",
                'participant_count': b.participant_count,
                'description': b.description or "", 
                'additional_requests': b.additional_requests or "",
                'additional_notes': b.additional_notes or "",
                'participants': participants_data
            },
        })
    return JsonResponse(events, safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id'); start_str = data.get('start_time'); end_str = data.get('end_time')
        if not all([booking_id, start_str, end_str]): return JsonResponse({'status': 'error', 'message': f"Missing required data."})
        
        booking = get_object_or_404(Booking, pk=booking_id)
        
        # 💡 [FIX] ใช้วิธีเช็คสิทธิ์แบบใหม่ (จาก model)
        if not booking.can_user_edit_or_cancel(request.user):
            return JsonResponse({'status': 'error', 'message': f"Permission denied (อาจจะเลยเวลาแล้ว)."}, status=403)

        try:
            new_start = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace(' ', '+'))
            new_end = datetime.fromisoformat(end_str.replace('Z', '+00:00').replace(' ', '+'))
        except ValueError: return JsonResponse({'status': 'error', 'message': f"Invalid date format."})
        if new_end <= new_start: return JsonResponse({'status': 'error', 'message': f"End time must be after start time."})
        
        if booking.room.is_currently_under_maintenance:
            return JsonResponse({'status': 'error', 'message': f"ไม่สามารถแก้ไขการจองได้: ห้อง '{booking.room.name}' กำลังปิดปรับปรุง"}, status=400)
        
        conflicts = Booking.objects.filter( 
            room=booking.room, 
            start_time__lt=new_end, 
            end_time__gt=new_start,
            status__in=['APPROVED', 'PENDING']
        ).exclude(pk=booking.id)
        
        if conflicts.exists(): return JsonResponse({'status': 'error', 'message': f"เลือกช่วงเวลาใหม่ไม่ได้ เนื่องจากเวลาทับซ้อนกับการจองอื่น"}, status=400)
        
        booking.start_time = new_start
        booking.end_time = new_end
        status_message = "Booking time updated successfully."
        if booking.participant_count >= 15 and booking.status not in ['PENDING', 'REJECTED', 'CANCELLED']:
            booking.status = 'PENDING'
            status_message = "Booking time updated. Approval now required."
        booking.save()
        
        if booking.outlook_event_id:
            try:
                access_token = _get_valid_outlook_token()
                if access_token:
                    client = OutlookClient(settings.AZURE_REDIRECT_URI)
                    client.update_calendar_event(access_token, booking.outlook_event_id, booking)
            except Exception as e:
                print(f"❌ Outlook Update Failed (API): {e}")
        
        AuditLog.objects.create(
            user=request.user,
            action='BOOKING_EDITED',
            ip_address=get_client_ip(request),
            details=f"Edited Booking ID {booking.id} ('{booking.title}') via Drag&Drop"
        )
        
        return JsonResponse({'status': 'success', 'message': status_message, 'new_status': booking.status})
    except json.JSONDecodeError: return JsonResponse({'status': 'error', 'message': f"Invalid JSON data."})
    except Booking.DoesNotExist: return JsonResponse({'status': 'error', 'message': f"Booking not found."})
    except Exception as e:
        print(f"Error in update_booking_time_api: {e}")
        return JsonResponse({'success': False, 'error': f"เกิดข้อผิดพลาดบนเซิร์ฟเวอร์"})

@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id):
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        
        # 💡 [FIX] ใช้วิธีเช็คสิทธิ์แบบใหม่ (จาก model)
        if not booking.can_user_edit_or_cancel(request.user):
            return JsonResponse({'success': False, 'error': f"ไม่มีสิทธิ์ยกเลิก (อาจจะเลยเวลาแล้ว)"}, status=403)

        if booking.status in ['CANCELLED', 'REJECTED']: return JsonResponse({'success': False, 'error': f"การจองนี้ถูกยกเลิกหรือปฏิเสธไปแล้ว"})
        
        if booking.room.is_currently_under_maintenance and not is_admin(request.user):
            messages.error(request, f"ไม่สามารถยกเลิกการจองได้: ห้อง '{booking.room.name}' กำลังปิดปรับปรุง")
            return JsonResponse({'success': False, 'error': f"ห้องกำลังปิดปรับปรุง"}, status=400)
            
        if booking.outlook_event_id:
            try:
                access_token = _get_valid_outlook_token()
                if access_token:
                    client = OutlookClient(settings.AZURE_REDIRECT_URI)
                    client.delete_calendar_event(access_token, booking.outlook_event_id)
                    booking.outlook_event_id = None 
            except Exception as e:
                print(f"❌ Outlook Deletion Failed (API): {e}")
        
        booking.status = 'CANCELLED'
        booking.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='BOOKING_CANCELLED',
            ip_address=get_client_ip(request),
            details=f"Cancelled Booking ID {booking.id} ('{booking.title}') via API"
        )
        
        return JsonResponse({'success': True, 'message': f"ยกเลิกการจองเรียบร้อย"})
    except Booking.DoesNotExist: return JsonResponse({'success': False, 'error': f"ไม่พบการจองนี้"}, status=44)
    except Exception as e:
        print(f"Error in delete_booking_api for booking {booking_id}: {e}")
        return JsonResponse({'success': False, 'error': f"เกิดข้อผิดพลาดบนเซิร์ฟเวอร์"})

# --- Booking CRUD Views ---
@login_required
@require_POST
@transaction.atomic 
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    
    if room.is_currently_under_maintenance and not is_admin(request.user):
        messages.error(request, f"ไม่สามารถจองได้: ห้อง '{room.name}' กำลังปิดปรับปรุง")
        context = get_base_context(request)
        form = BookingForm(request.POST, request.FILES)
        context.update({'room': room, 'form': form})
        return render(request, 'pages/room_calendar.html', context)

    form = BookingForm(request.POST, request.FILES) 
    
    if form.is_valid():
        try:
            recurrence = form.cleaned_data.get('recurrence')
            recurrence_end_date = form.cleaned_data.get('recurrence_end_date')
            start_time = form.cleaned_data.get('start_time')
            end_time = form.cleaned_data.get('end_time')
            participant_count = form.cleaned_data.get('participant_count', 1)

            new_status = 'APPROVED'
            if participant_count >= 15:
                new_status = 'PENDING'

            parent_booking = form.save(commit=False)
            parent_booking.room = room
            parent_booking.user = request.user
            parent_booking.status = new_status
            
            parent_booking.clean() 
            
            conflicts = Booking.objects.filter(
                room=room,
                status__in=['APPROVED', 'PENDING'],
                start_time__lt=parent_booking.end_time,
                end_time__gt=parent_booking.start_time
            ).exists()
            
            if conflicts:
                # 💡 [FIX] ตอบกลับด้วย 400 Bad Request เพื่อให้ Ajax รู้ว่าล้มเหลว
                return HttpResponse(f"Validation Error: ไม่สามารถจองได้: ช่วงเวลาที่คุณเลือกทับซ้อนกับการจองอื่น", status=400)

            if participant_count >= 15:
                parent_booking.status = 'PENDING'
                messages.success(request, f"จอง '{parent_booking.title}' ({room.name}) เรียบร้อย **รออนุมัติ**")
            else:
                parent_booking.status = 'APPROVED'
                messages.success(request, f"จอง '{parent_booking.title}' ({room.name}) **อนุมัติอัตโนมัติ**")
            
            parent_booking.save() 
            form.save_m2m() 
            
            if parent_booking.status == 'APPROVED': 
                try:
                    access_token = _get_valid_outlook_token()
                    if access_token:
                        client = OutlookClient(settings.AZURE_REDIRECT_URI)
                        outlook_response = client.create_calendar_event(access_token, parent_booking)
                        parent_booking.outlook_event_id = outlook_response.get('id')
                        parent_booking.save()
                        messages.success(request, "การจองถูกสร้างและเพิ่มในปฏิทิน Outlook แล้ว!")
                except Exception as e:
                    print(f"❌ Outlook Creation Failed: {e}") 
                    messages.warning(request, "การจองถูกสร้างแล้ว แต่ไม่สามารถเพิ่มในปฏิทิน Outlook ได้")

            AuditLog.objects.create(
                user=request.user,
                action='BOOKING_CREATED',
                ip_address=get_client_ip(request),
                details=f"Created Booking ID {parent_booking.id} ('{parent_booking.title}')"
            )
            
            if parent_booking.status == 'PENDING':
                send_booking_notification(parent_booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ')
            else:
                send_booking_notification(parent_booking, 'emails/new_booking_approved.html', 'จองสำเร็จ')
            
            if recurrence and recurrence != 'NONE':
                
                parent_booking.recurrence_rule = recurrence 
                parent_booking.save()
                
                next_start_time = start_time
                next_end_time = end_time
                
                participants = list(parent_booking.participants.all())

                while True:
                    if recurrence == 'WEEKLY':
                        next_start_time += timedelta(weeks=1)
                        next_end_time += timedelta(weeks=1) 
                    elif recurrence == 'MONTHLY':
                        next_start_time += relativedelta(months=1)
                        next_end_time += relativedelta(months=1) 
                    
                    if next_start_time.date() > recurrence_end_date:
                        break
                        
                    child_conflicts = Booking.objects.filter(
                        room=room,
                        status__in=['APPROVED', 'PENDING'],
                        start_time__lt=next_end_time,
                        end_time__gt=next_start_time
                    ).exists()

                    if not child_conflicts:
                        try:
                            new_booking = Booking(
                                parent_booking=parent_booking, 
                                room=room,
                                user=request.user,
                                title=parent_booking.title,
                                start_time=next_start_time,
                                end_time=next_end_time,
                                chairman=parent_booking.chairman,
                                department=parent_booking.department,
                                participant_count=parent_booking.participant_count,
                                description=parent_booking.description,
                                additional_requests=parent_booking.additional_requests,
                                additional_notes=parent_booking.additional_notes,
                                status=new_status,
                                recurrence_rule=recurrence
                            )
                            new_booking.save() 
                            new_booking.participants.set(participants) 
                        except Exception as e:
                            print(f"Error creating recurring child booking: {e}")
                    else:
                        print(f"Skipping recurring booking on {next_start_time.date()} due to conflict.")
                
            # 💡 [FIX] ตอบกลับด้วย 200 OK เพื่อให้ Ajax (ใน room_calendar.html) รู้ว่าสำเร็จ
            return HttpResponse("Booking created successfully.", status=200)

        except ValidationError as e:
            error_str = ", ".join(e.messages)
            # 💡 [FIX] ตอบกลับด้วย 400 Bad Request เพื่อให้ Ajax รู้ว่าล้มเหลว
            return HttpResponse(f"Validation Error: {error_str}", status=400)
    
    # 💡 [FIX] ถ้าฟอร์มไม่ valid (เช่น ขาด Title)
    error_list = []
    for field, errors in form.errors.items():
        field_label = form.fields.get(field).label if field != '__all__' and field in form.fields else (field if field != '__all__' else 'Form')
        error_list.append(f"{field_label}: {', '.join(errors)}")
    error_str = "; ".join(error_list)
    return HttpResponse(f"Invalid Form: {error_str}", status=400)

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    
    # 💡 [FIX] ใช้วิธีเช็คสิทธิ์แบบใหม่ (จาก model)
    if not booking.can_user_edit_or_cancel(request.user):
        messages.error(request, f"คุณไม่มีสิทธิ์แก้ไขการจองนี้ (อาจจะเนื่องจากเวลาผ่านไปแล้ว)")
        
        # 💡 [FIX] ถ้ามาจาก Ajax (Modal) ให้ส่ง Error กลับไป
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse("Permission Denied: คุณไม่มีสิทธิ์แก้ไขการจองนี้ (อาจจะเลยเวลาแล้ว)", status=403)
        return redirect('history')
        
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            try:
                updated_booking = form.save(commit=False)
                
                if updated_booking.room.is_currently_under_maintenance and not is_admin(request.user):
                    # 💡 [FIX] ตอบกลับ Error ให้ Ajax
                    error_msg = f"ไม่สามารถแก้ไขการจองได้: ห้อง '{updated_booking.room.name}' กำลังปิดปรับปรุง"
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return HttpResponse(error_msg, status=400)
                    messages.error(request, error_msg)
                    context = get_base_context(request)
                    context.update({'form': form, 'booking': booking})
                    return render(request, 'pages/edit_booking.html', context)
                
                updated_booking.clean() 
                new_count = form.cleaned_data.get('participant_count', 1)
                changed_for_approval = any(f in form.changed_data for f in ['start_time', 'end_time', 'participant_count'])
                if new_count >= 15 and changed_for_approval and updated_booking.status not in ['PENDING', 'REJECTED', 'CANCELLED']:
                    updated_booking.status = 'PENDING'
                    messages.info(request, f"การแก้ไขต้องรอการอนุมัติใหม่")
                updated_booking.save()
                form.save_m2m() 
                
                if updated_booking.outlook_event_id:
                    try:
                        access_token = _get_valid_outlook_token()
                        if access_token:
                            client = OutlookClient(settings.AZURE_REDIRECT_URI)
                            client.update_calendar_event(access_token, updated_booking.outlook_event_id, updated_booking)
                            messages.success(request, "การจองถูกแก้ไขและอัปเดตในปฏิทิน Outlook แล้ว!")
                    except Exception as e:
                        print(f"❌ Outlook Update Failed (API): {e}")
                        messages.warning(request, "การจองถูกแก้ไขแล้ว แต่ไม่สามารถอัปเดตในปฏิทิน Outlook ได้")

                messages.success(request, f"แก้ไขข้อมูลการจองเรียบร้อยแล้ว")
                
                AuditLog.objects.create(
                    user=request.user,
                    action='BOOKING_EDITED',
                    ip_address=get_client_ip(request),
                    details=f"Edited Booking ID {updated_booking.id} ('{updated_booking.title}')"
                )
                
                if updated_booking.status == 'PENDING' and changed_for_approval:
                    send_booking_notification(updated_booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ (แก้ไข)')
                
                # 💡 [FIX] ตรวจสอบว่า request มาจาก Ajax (Modal) หรือไม่
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': 'Booking updated'})
                
                return redirect('history')
                
            except ValidationError as e:
                error_str = ", ".join(e.messages)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return HttpResponse(f"Validation Error: {error_str}", status=400)
                form.add_error(None, e)
                messages.error(request, f"ไม่สามารถบันทึกได้: {error_str}")
    else: 
        form = BookingForm(instance=booking)
    
    context = get_base_context(request)
    context.update({'form': form, 'booking': booking})
    return render(request, 'pages/edit_booking.html', context)

@login_required
@require_POST
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    
    # 💡 [FIX] ใช้วิธีเช็คสิทธิ์แบบใหม่ (จาก model)
    if not booking.can_user_edit_or_cancel(request.user):
        messages.error(request, f"คุณไม่มีสิทธิ์ยกเลิกการจองนี้ (อาจจะเนื่องจากเวลาผ่านไปแล้ว)")
        return redirect('history')

    if booking.status in ['CANCELLED', 'REJECTED']:
        messages.warning(request, f"การจองนี้ถูกยกเลิกหรือปฏิเสธไปแล้ว")
        return redirect('history')
        
    if booking.room.is_currently_under_maintenance and not is_admin(request.user):
        messages.error(request, f"ไม่สามารถยกเลิกการจองได้: ห้อง '{booking.room.name}' กำลังปิดปรับปรุง")
        return redirect('history')
        
    if booking.outlook_event_id:
        try:
            access_token = _get_valid_outlook_token()
            if access_token:
                client = OutlookClient(settings.AZURE_REDIRECT_URI)
                client.delete_calendar_event(access_token, booking.outlook_event_id)
                booking.outlook_event_id = None 
                messages.success(request, "การจองถูกยกเลิกและลบออกจากปฏิทิน Outlook แล้ว!")
        except Exception as e:
            print(f"❌ Outlook Deletion Failed (API): {e}")
            messages.warning(request, "การจองถูกยกเลิกแล้ว แต่ไม่สามารถลบออกจากปฏิทิน Outlook ได้")
        
    booking.status = 'CANCELLED'
    booking.save()
    
    AuditLog.objects.create(
        user=request.user,
        action='BOOKING_CANCELLED',
        ip_address=get_client_ip(request),
        details=f"Cancelled Booking ID {booking.id} ('{booking.title}')"
    )
    
    messages.success(request, f"ยกเลิกการจอง '{booking.title}' เรียบร้อย")
    return redirect('history')

# --- (โค้ด Approvals... เหมือนเดิม) ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    
    if is_admin(request.user):
        pending_query = Q(room__approver=request.user) | Q(room__approver__isnull=True)
    else:
        pending_query = Q(room__approver=request.user)
        
    pending_bookings = Booking.objects.filter(pending_query, status='PENDING') \
                                        .select_related('room', 'user') \
                                        .order_by('start_time')
                                        
    context = get_base_context(request)
    context.update({'pending_bookings': pending_bookings})
    return render(request, 'pages/approvals.html', context)
@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('user', 'room'), id=booking_id, status='PENDING')
    
    if booking.room.is_currently_under_maintenance:
        messages.error(request, f"ไม่สามารถอนุมัติได้: ห้อง '{booking.room.name}' กำลังปิดปรับปรุงในช่วงเวลานี้")
        return redirect('approvals')
    
    if not (is_admin(request.user) or (booking.room.approver == request.user)):
        messages.error(request, f"คุณไม่มีสิทธิ์อนุมัติการจองนี้")
        return redirect('approvals')

    # --- 💡 [ใหม่] OUTLOOK CALENDAR INTEGRATION (CREATE/UPDATE) ---
    try:
        access_token = _get_valid_outlook_token()
        if access_token:
            client = OutlookClient(settings.AZURE_REDIRECT_URI)
            
            if booking.outlook_event_id:
                # Update Event ถ้ามีอยู่แล้ว
                client.update_calendar_event(access_token, booking.outlook_event_id, booking)
            else:
                # สร้าง Event ใหม่
                outlook_response = client.create_calendar_event(access_token, booking)
                booking.outlook_event_id = outlook_response.get('id')
                messages.success(request, "Event ถูกสร้างในปฏิทิน Outlook แล้ว!")
        else:
            messages.warning(request, "ไม่สามารถสร้าง Event ใน Outlook ได้ (Admin ต้องเชื่อมต่อก่อน)")
    except Exception as e:
        print(f"❌ Outlook Approval Error: {e}")
        messages.warning(request, "อนุมัติสำเร็จ แต่เกิดข้อผิดพลาดในการเชื่อมต่อ Outlook")
    # --- สิ้นสุด OUTLOOK CALENDAR INTEGRATION ---
    
    booking.status = 'APPROVED'
    booking.save()
    
    AuditLog.objects.create(
        user=request.user,
        action='BOOKING_APPROVED',
        ip_address=get_client_ip(request),
        details=f"Approved Booking ID {booking.id} ('{booking.title}')"
    )
    send_booking_notification(booking, 'emails/booking_approved_user.html', 'การจองของคุณอนุมัติแล้ว')
    
    messages.success(request, f"อนุมัติการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')
@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('user', 'room'), id=booking_id, status='PENDING')

    if not (is_admin(request.user) or (booking.room.approver == request.user)):
        messages.error(request, f"คุณไม่มีสิทธิ์ปฏิเสธการจองนี้")
        return redirect('approvals')
        
    booking.status = 'REJECTED'
    booking.save()
    
    AuditLog.objects.create(
        user=request.user,
        action='BOOKING_REJECTED',
        ip_address=get_client_ip(request),
        details=f"Rejected Booking ID {booking.id} ('{booking.title}')"
    )
    send_booking_notification(booking, 'emails/booking_rejected_user.html', 'การจองของคุณถูกปฏิเสธ')
    
    messages.warning(request, f"ปฏิเสธการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')

# --- (โค้ด Teams... เหมือนเดิม) ---
@require_POST
def teams_action_receiver(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        booking_id = data.get('bookingId')
        action = data.get('action') # 'approve' หรือ 'reject'
        if not booking_id or not action:
            return JsonResponse({'status': 'error', 'message': 'Missing bookingId or action.'}, status=400)
        booking = get_object_or_404(Booking.objects.select_related('room'), pk=booking_id)
        if booking.status != 'PENDING':
            return _update_teams_card_after_action(booking, 'COMPLETED', action)
        if action == 'approve':
            booking.status = 'APPROVED'
            booking.save()
            send_booking_notification(booking, 'emails/booking_approved_user.html', 'การจองของคุณอนุมัติแล้ว')
            if booking.outlook_event_id:
                _update_outlook_after_teams_action(booking)
            return _update_teams_card_after_action(booking, 'APPROVED', action)
        elif action == 'reject':
            booking.status = 'REJECTED'
            booking.save()
            send_booking_notification(booking, 'emails/booking_rejected_user.html', 'การจองของคุณถูกปฏิเสธ')
            return _update_teams_card_after_action(booking, 'REJECTED', action)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action.'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
    except Booking.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Booking not found.'}, status=404)
    except Exception as e:
        print(f"Error in teams_action_receiver: {e}")
        return JsonResponse({'status': 'error', 'message': f'Server Error: {e}'}, status=500)
def _update_outlook_after_teams_action(booking):
    if booking.outlook_event_id:
        try:
            access_token = _get_valid_outlook_token()
            if access_token:
                client = OutlookClient(settings.AZURE_REDIRECT_URI)
                if booking.status == 'APPROVED':
                    client.update_calendar_event(access_token, booking.outlook_event_id, booking)
                elif booking.status in ['REJECTED', 'CANCELLED']:
                    client.delete_calendar_event(access_token, booking.outlook_event_id)
        except Exception as e:
            print(f"❌ Outlook Sync Error after Teams Action: {e}")
def _update_teams_card_after_action(booking, new_status, action_type):
    new_card = {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"✅ การจอง {booking.title} ได้รับการประมวลผลแล้ว", "weight": "Bolder", "size": "Medium", "color": "Good"},
            {"type": "TextBlock", "text": f"ดำเนินการโดย Teams Interactive Action\n**สถานะล่าสุด:** {new_status} (โดย {action_type.upper()})", "wrap": True, "separator": True},
            {"type": "FactSet", "facts": [{"title": "ห้อง:", "value": booking.room.name}, {"title": "เวลา:", "value": f"{booking.start_time.strftime('%d/%m %H:%M')} - {booking.end_time.strftime('%H:%M')}"}]}
        ]
    }
    return JsonResponse(new_card, safe=False, status=200, headers={'Content-Type': 'application/vnd.microsoft.card.adaptive'})

# --- (โค้ด Management... เหมือนเดิม) ---
@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    users = User.objects.all().order_by('username').prefetch_related('groups')
    context = get_base_context(request)
    context.update({'users': users})
    return render(request, 'pages/user_management.html', context)
@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    user_to_edit = get_object_or_404(User, pk=user_id)
    all_groups = Group.objects.all()
    if request.method == 'POST':
        selected_group_ids = request.POST.getlist('groups')
        selected_groups = Group.objects.filter(pk__in=selected_group_ids)
        user_to_edit.groups.set(selected_groups)
        user_to_edit.is_staff = (is_admin(user_to_edit) or user_to_edit.is_superuser)
        user_to_edit.save()
        messages.success(request, f"อัปเดตสิทธิ์ผู้ใช้ '{user_to_edit.username}' เรียบร้อย")
        return redirect('user_management')
    context = get_base_context(request)
    context.update({
       'user_to_edit': user_to_edit,
       'all_groups': all_groups,
       'user_group_pks': list(user_to_edit.groups.values_list('pk', flat=True))
    })
    return render(request, 'pages/edit_user_roles.html', context)
@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    rooms = Room.objects.all().order_by('building', 'name')
    context = get_base_context(request)
    context.update({'rooms': rooms})
    return render(request, 'pages/rooms.html', context)
@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, f"เพิ่มห้องประชุมใหม่เรียบร้อย")
            return redirect('rooms')
        else:
            messages.error(request, f"ไม่สามารถเพิ่มห้องได้ กรุณาตรวจสอบข้อผิดพลาด")
    else: 
        form = RoomForm()
    context = get_base_context(request)
    context.update({'form': form, 'title': 'เพิ่มห้องประชุมใหม่'})
    return render(request, 'pages/room_form.html', context)
@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    if request.method == 'POST':
        form = RoomForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, f"แก้ไขข้อมูลห้อง '{room.name}' เรียบร้อย")
            return redirect('rooms') 
        else:
            messages.error(request, f"ไม่สามารถแก้ไขห้อง '{room.name}' ได้ กรุณาตรวจสอบข้อผิดพลาด") 
    else: 
        form = RoomForm(instance=room)
    context = get_base_context(request)
    context.update({'form': form, 'title': f'แก้ไขข้อมูลห้อง: {room.name}'})
    return render(request, 'pages/room_form.html', context)
@login_required
@user_passes_test(is_admin)
@require_POST
def delete_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    room_name = room.name
    try:
        room.delete()
        messages.success(request, f"ลบห้อง '{room_name}' เรียบร้อย")
    except Exception as e:
        messages.error(request, f"ไม่สามารถลบห้อง '{room_name}' ได้: {e}")
    return redirect('rooms')

@login_required
@user_passes_test(is_admin) 
def audit_log_view(request):
    log_list = AuditLog.objects.all().select_related('user').order_by('-timestamp')
    
    paginator = Paginator(log_list, 25) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_base_context(request)
    context.update({'page_obj': page_obj})
    return render(request, 'pages/audit_log.html', context)

# -----------------------------------------------
# 💡 [FIX 4] REPORTS & PDF EXPORT (เปลี่ยนมาใช้ WeasyPrint)
# -----------------------------------------------

# ❌ เราลบฟังก์ชัน render_to_pdf() (ของ xhtml2pdf) ทิ้งไป

@login_required
@user_passes_test(is_admin)
def reports_view(request):
    # (โค้ด reports_view ยังคงเหมือนเดิมทุกประการ)
    period = request.GET.get('period', 'monthly')
    department = request.GET.get('department', '')
    today = timezone.now().date()
    start_date = today
    
    if period == 'daily':
        start_date = today; report_title = f'รายงานการใช้งานรายวัน ({today:%d %b %Y})'
    elif period == 'weekly':
        start_date = today - timedelta(days=6); report_title = f'รายงานการใช้งานรายสัปดาห์ ({start_date:%d %b} - {today:%d %b %Y})'
    else:
        start_date = today - timedelta(days=29); report_title = f'รายงานการใช้งานรายเดือน ({start_date:%d %b} - {today:%d %b %Y})'

    booking_filter = Q(bookings__start_time__date__gte=start_date, bookings__start_time__date__lte=today, bookings__status='APPROVED')
    if department:
        booking_filter &= Q(bookings__department=department); report_title += f" (แผนก: {department})"

    room_usage_stats = Room.objects.filter(is_maintenance=False).annotate(
        booking_count=Count('bookings', filter=booking_filter)
    ).filter(booking_count__gt=0).order_by('-booking_count')
    room_usage_labels = [r.name for r in room_usage_stats[:10]]
    room_usage_data = [r.booking_count for r in room_usage_stats[:10]]
    
    dept_booking_filter = Q(start_time__date__gte=start_date, start_time__date__lte=today, status='APPROVED')
    if department:
        dept_booking_filter &= Q(department=department)

    dept_usage_query = Booking.objects.filter(dept_booking_filter) \
                                        .exclude(department__exact='').exclude(department__isnull=True) \
                                        .values('department').annotate(count=Count('id')).order_by('-count')
    dept_usage_labels = [d['department'] for d in dept_usage_query[:10] if d.get('department')]
    dept_usage_data = [d['count'] for d in dept_usage_query[:10] if d.get('department')]
    departments_dropdown = Booking.objects.exclude(department__exact='').exclude(department__isnull=True) \
                                            .values_list('department', flat=True).distinct().order_by('department')
    
    context = get_base_context(request)
    context.update({
        'room_usage_stats': room_usage_stats, 'report_title': report_title,
        'all_departments': departments_dropdown, 'current_period': period,
        'current_department': department, 'room_usage_labels': json.dumps(room_usage_labels),
        'room_usage_data': json.dumps(room_usage_data), 'dept_usage_labels': json.dumps(dept_usage_labels),
        'dept_usage_data': json.dumps(dept_usage_data), 'pending_count': context['pending_count'],
        'today_bookings_count': Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count(),
        'total_users_count': User.objects.count(),
        'total_rooms_count': Room.objects.filter(is_maintenance=False).count(), 'login_history': [], 
    })
    return render(request, 'pages/reports.html', context)
@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    # (โค้ด Excel เหมือนเดิม ไม่มีการเปลี่ยนแปลง)
    try:
        from openpyxl import Workbook
    except ImportError:
        messages.error(request, f"ไม่สามารถส่งออกเป็น Excel ได้: ไม่ได้ติดตั้งไลบรารี openpyxl")
        return redirect('reports')
    period = request.GET.get('period', 'monthly'); department = request.GET.get('department', '')
    today = timezone.now().date(); start_date = today
    if period == 'daily': start_date = today
    elif period == 'weekly': start_date = today - timedelta(days=6)
    else: start_date = today - timedelta(days=29)
    bookings = Booking.objects.filter(start_time__date__gte=start_date, start_time__date__lte=today, status='APPROVED').select_related('room', 'user').order_by('start_time')
    if department: bookings = bookings.filter(department=department)
    wb = Workbook(); ws = wb.active; ws.title = f"Report {start_date} to {today}"
    headers = ["ID", "Title", "Room", "Booked By", "Department", "Start Time", "End Time", "Participants"]
    ws.append(headers)
    for b in bookings:
        booked_by_name = b.user.get_full_name() or b.user.username if b.user else '(User ถูกลบ)'
        ws.append([b.id, b.title, b.room.name, booked_by_name, b.department,
                   b.start_time.strftime('%Y-%m-%d %H:%M'), b.end_time.strftime('%Y-%m-%d %H:%M'), b.participant_count])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=booking_report_{today}.xlsx'
    wb.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    """
    [FIX 4] เปลี่ยนมาใช้ WeasyPrint
    (ฟังก์ชันนี้จะใช้ Template 'pages/reports_pdf.html' ตัวที่มี @font-face)
    """
    
    # 1. ดึงข้อมูล (Logic เดิม)
    period = request.GET.get('period', 'monthly'); department = request.GET.get('department', '')
    today = timezone.now().date(); start_date = today
    if period == 'daily':
        start_date = today; report_title = f'รายงานการใช้งานรายวัน ({today:%d %b %Y})'
    elif period == 'weekly':
        start_date = today - timedelta(days=6); report_title = f'รายงานการใช้งานรายสัปดาห์ ({start_date:%d %b} - {today:%d %b %Y})'
    else:
        start_date = today - timedelta(days=29); report_title = f'รายงานการใช้งานรายเดือน ({start_date:%d %b} - {today:%d %b %Y})'

    booking_filter = Q(start_time__date__gte=start_date, start_time__date__lte=today, status='APPROVED')
    if department:
        booking_filter &= Q(department=department); report_title += f" (แผนก: {department})"
    recent_bookings = Booking.objects.filter(booking_filter).select_related('room', 'user').order_by('start_time')
    
    # 2. [สำคัญ] หา Path ของฟอนต์ (Logic ใหม่ที่ใช้ HTTP)
    font_url = None
    try:
        # หา URL แบบ /static/fonts/Sarabun-Regular.ttf
        font_url = staticfiles_storage.url('fonts/Sarabun-Regular.ttf')
    except ValueError:
        print("!!! ERROR (WeasyPrint): หา Sarabun-Regular.ttf ไม่เจอ, ลองหา THSarabunNew.ttf")
        try:
            font_url = staticfiles_storage.url('fonts/THSarabunNew.ttf')
        except ValueError:
            print("!!! CRITICAL ERROR (WeasyPrint): ไม่พบไฟล์ฟอนต์"); font_url = None
    
    # 3. สร้าง Context
    context = {
        'bookings': recent_bookings,
        'report_title': report_title,
        'export_date': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'), # 💡 [FIX] ใช้ localtime
        'font_url': font_url, # 💡 ส่ง /static/fonts/...
    }

    # 4. Render PDF ด้วย WeasyPrint
    html_string = render_to_string('pages/reports_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="weasyprint_report_{today}.pdf"'
    
    # [สำคัญ] WeasyPrint ต้องการ 'base_url'
    base_url = request.build_absolute_uri('/')
    
    try:
        HTML(string=html_string, base_url=base_url).write_pdf(response)
        print("--- WeasyPrint สร้าง PDF สำเร็จ ---")
        return response
        
    except Exception as e:
        print(f"!!! CRITICAL WEASYPRINT ERROR: {e}")
        # (นี่คือจุดที่ 'Fontconfig error' อาจจะแสดงผลถ้า GTK3 หายไป)
        messages.error(request, f"เกิดข้อผิดพลาดร้ายแรงกับ WeasyPrint: {e}. กรุณาตรวจสอบว่าติดตั้ง GTK3 บน Windows และรีสตาร์ทเครื่องแล้ว")

        return redirect('reports')