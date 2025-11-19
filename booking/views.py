import json
import re
import requests
from datetime import datetime, timedelta, time
import os
from collections import defaultdict
from dateutil.relativedelta import relativedelta

# Imports สำหรับ WeasyPrint
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
from django.views.generic import View

# Import Models และ Forms
from .models import Room, Booking, AuditLog, OutlookToken 
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm
from .outlook_client import OutlookClient 
    
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

# --- Callbacks / Notification Helpers ---
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

@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    pass 

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
        return

    if not isinstance(recipients, list): recipients = [recipients]
    subject = f"[{subject_prefix}] การจองห้อง: {booking.title} ({booking.room.name})"
    context = {'booking': booking, 'settings': settings}
    try:
        message_html = render_to_string(template_name, context)
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
            send_mail(subject, message_html, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=message_html)
        else:
            send_mail(subject, "Fallback text", settings.DEFAULT_FROM_EMAIL, recipients, html_message=message_html)
    except Exception as e: 
        print(f"Error preparing/sending email '{subject}': {e}")

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
    if request.user.is_authenticated: 
        return redirect('dashboard')
    
    context = {}
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST);
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, "บัญชีผู้ใช้ของคุณไม่สามารถใช้งานได้")
                return redirect('login') 
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            messages.success(request, f"ยินดีต้อนรับ, {user.get_full_name() or user.username}!")
            return redirect(next_url)
        else:
            if form.errors:
                messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้ง")
    else: 
        form = AuthenticationForm()
    context.update({'form': form})
    return render(request, 'login_card.html', context) 

def sso_login_view(request):
    messages.info(request, "ระบบ SSO ยังไม่เปิดใช้งานในขณะนี้")
    return redirect('login') 

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, f"คุณได้ออกจากระบบเรียบร้อยแล้ว");
    return redirect('login') 

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

def public_calendar_view(request):
    """ แสดงปฏิทินรวมสำหรับผู้ใช้สาธารณะ """
    all_rooms = Room.objects.all().exclude(is_maintenance=True).order_by('building', 'floor', 'name')
    context = get_base_context(request)
    context.update({
        'all_rooms': all_rooms,
        'is_public_view': True,
    })
    return render(request, 'pages/master_calendar.html', context)


# ----------------------------------------------------------------------
# C. SMART SEARCH
# ----------------------------------------------------------------------

def parse_search_query(query_text):
    from datetime import datetime, time, timedelta 
    capacity = None; start_time = None; end_time = None
    now = timezone.now(); today = now.date()
    
    capacity_match = re.search(r'(\d+)\s*คน', query_text)
    if capacity_match: capacity = int(capacity_match.group(1))
    
    if "บ่ายนี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, time(13, 0))) 
        end_time = timezone.make_aware(datetime.combine(today, time(17, 0)))
    elif "เช้านี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, time(12, 0)))
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


# ----------------------------------------------------------------------
# D. MAIN PAGES (Dashboard, Calendar, History, Detail)
# ----------------------------------------------------------------------

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
            room.status = 'ปิดปรับปรุง'; room.status_class = 'status-maintenance'
            room.current_booking_info = None; room.next_booking_info = None
        else:
            # 💡 [FIX] ตรวจสอบทั้ง APPROVED และ PENDING ให้หน้า Dashboard
            current = room.bookings.filter(
                start_time__lte=now, end_time__gt=now, 
                status__in=['APPROVED', 'PENDING']
            ).select_related('user').first()
            
            if current:
                if current.status == 'PENDING':
                    room.status = 'รออนุมัติ'; room.status_class = 'bg-warning text-dark'
                else:
                    room.status = 'ไม่ว่าง'; room.status_class = 'status-occupied'
            else:
                room.status = 'ว่าง'; room.status_class = 'status-available'
            room.current_booking_info = current
            room.next_booking_info = None
            if not current:
                room.next_booking_info = room.bookings.filter(start_time__gt=now, status='APPROVED').select_related('user').order_by('start_time').first()
        buildings[room.building or "(ไม่ได้ระบุอาคาร)"].append(room)
        
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
    """ 🚨 [FIXED] บันทึกการจอง + แจ้ง Error ชัดเจน """
    room = get_object_or_404(Room, pk=room_id)
    
    if room.is_currently_under_maintenance and not is_admin(request.user):
        messages.error(request, f"ห้อง '{room.name}' กำลังปิดปรับปรุงชั่วคราว")
        return redirect('dashboard') 
        
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES) 
        
        if form.is_valid():
            try:
                booking = form.save(commit=False)
                
                # 💡 [NEW LOGIC] เงื่อนไขการอนุมัติ
                participant_count = form.cleaned_data.get('participant_count', 0)
                
                # เช็คอุปกรณ์ (ถ้ามีในฟอร์ม)
                has_equipment = False
                if 'equipments' in form.cleaned_data:
                    has_equipment = form.cleaned_data['equipments'].exists()

                if participant_count >= 15 or has_equipment:
                    booking.status = 'PENDING'
                    status_msg = "รอการอนุมัติ (คนเยอะ/มีอุปกรณ์)"
                else:
                    booking.status = 'APPROVED'
                    status_msg = "จองสำเร็จ"

                booking.room = room
                booking.user = request.user
                booking.save()
                form.save_m2m() # บันทึก ManyToMany
                
                # สร้าง Outlook Event (ถ้าอนุมัติแล้ว)
                if booking.status == 'APPROVED':
                     try:
                        token = _get_valid_outlook_token()
                        if token:
                            client = OutlookClient(settings.AZURE_REDIRECT_URI)
                            res = client.create_calendar_event(token, booking)
                            booking.outlook_event_id = res.get('id')
                            booking.save()
                     except Exception: pass

                messages.success(request, f"บันทึกการจองเรียบร้อย: {status_msg}")
                return redirect('room_calendar', room_id=room.id)
            except Exception as e:
                messages.error(request, f"เกิดข้อผิดพลาดระบบ: {e}")
        else:
            # 🚨 แจ้ง Error จาก Form ให้ชัดเจน
            first_err = next(iter(form.errors.values()))[0]
            messages.error(request, f"ข้อมูลไม่ถูกต้อง: {first_err}")
             
    else:
        initial_data = {'room': room}
        if request.GET.get('start') and request.GET.get('end'):
            initial_data['start_time'] = request.GET['start']
            initial_data['end_time'] = request.GET['end']
        form = BookingForm(initial=initial_data)
        
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
    """ แสดง Master Calendar สำหรับผู้ใช้ที่ล็อกอินแล้ว """
    all_rooms = Room.objects.all().exclude(is_maintenance=True).order_by('building', 'floor', 'name')
    context = get_base_context(request)
    context.update({ 'all_rooms': all_rooms })
    return render(request, 'pages/master_calendar.html', context)


@login_required
def history_view(request): 
    if is_admin(request.user):
        bookings = Booking.objects.all().select_related('room', 'user').order_by('-start_time')
    else:
        bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-start_time')
        
    date_f = request.GET.get('date'); room_f = request.GET.get('room'); status_f = request.GET.get('status'); q_f = request.GET.get('q', '')
    
    if date_f:
        try: bookings = bookings.filter(start_time__date=datetime.strptime(date_f, '%Y-%m-%d').date())
        except ValueError: pass
    if room_f:
        try: bookings = bookings.filter(room_id=int(room_f))
        except ValueError: pass
    if status_f: bookings = bookings.filter(status=status_f)
    if q_f:
        bookings = bookings.filter(Q(title__icontains=q_f) | Q(user__username__icontains=q_f))

    context = get_base_context(request)
    context.update({
        'bookings_list': bookings,  
        'all_rooms': Room.objects.all().order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
    })
    return render(request, 'pages/history.html', context)


def booking_detail_view(request, booking_id):
    """ อนุญาตให้ผู้ใช้ทุกคนดูรายละเอียดการจองได้ """
    booking = get_object_or_404(Booking, pk=booking_id)
    is_public_view = not request.user.is_authenticated
    
    context = get_base_context(request) 
    context.update({
        'booking': booking,
        'can_edit_or_cancel': booking.can_user_edit_or_cancel(request.user) if request.user.is_authenticated else False,
        'is_public_view': is_public_view,
    })
    return render(request, 'pages/booking_detail.html', context)

# ----------------------------------------------------------------------
# E. APPROVALS & CRUD VIEWS
# ----------------------------------------------------------------------

@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    if is_admin(request.user):
        pending_query = Q(room__approver=request.user) | Q(room__approver__isnull=True)
    else:
        pending_query = Q(room__approver=request.user)
    pending_bookings = Booking.objects.filter(pending_query, status='PENDING').order_by('start_time')
    context = get_base_context(request) 
    context.update({'pending_bookings': pending_bookings})
    return render(request, 'pages/approvals.html', context)

@login_required
@require_POST
def create_booking_view(request, room_id):
    return room_calendar_view(request, room_id) # Use same logic

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if not booking.can_user_edit_or_cancel(request.user):
        messages.error(request, "ไม่มีสิทธิ์แก้ไข")
        return redirect('history')
        
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            booking_obj = form.save(commit=False)
            p_count = form.cleaned_data.get('participant_count', 0)
            has_eq = False
            if 'equipments' in form.cleaned_data: has_eq = form.cleaned_data['equipments'].exists()
            
            if p_count >= 15 or has_eq:
                booking_obj.status = 'PENDING'
                messages.info(request, "การแก้ไขนี้ต้องรอการอนุมัติใหม่")
            
            booking_obj.save()
            form.save_m2m()
            messages.success(request, "แก้ไขเรียบร้อย")
            return redirect('history')
    else:
        form = BookingForm(instance=booking)
        
    context = get_base_context(request)
    context.update({'form': form, 'booking': booking})
    return render(request, 'pages/edit_booking.html', context)

@login_required
@require_POST
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.can_user_edit_or_cancel(request.user):
        booking.status = 'CANCELLED'
        booking.save()
        messages.success(request, "ยกเลิกสำเร็จ")
    return redirect('history')

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, "อนุมัติแล้ว")
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.success(request, "ปฏิเสธแล้ว")
    return redirect('approvals')

# ----------------------------------------------------------------------
# F. OUTLOOK & APIs
# ----------------------------------------------------------------------

def _get_valid_outlook_token():
    return None
@login_required
@user_passes_test(is_admin)
def outlook_connect(request):
    pass
@login_required
@user_passes_test(is_admin)
def outlook_callback(request):
    pass

# 🚨 [CRITICAL FIX] ปลดล็อก API (ลบ @login_required)
def rooms_api(request):
    rooms = Room.objects.all().exclude(is_maintenance=True).order_by('building', 'name')
    resources = [{
        'id': r.id, 
        'title': r.name or "", 
        'building': r.building or "",
        'capacity': r.capacity, 
        'floor': r.floor or ""
    } for r in rooms]
    return JsonResponse(resources, safe=False)

# 🚨 [CRITICAL FIX] ปลดล็อก API และแสดงรายการรออนุมัติ
def bookings_api(request):
    start_str = request.GET.get('start'); end_str = request.GET.get('end'); room_id = request.GET.get('room_id')
    if not start_str or not end_str: return JsonResponse({'error': 'Missing params'}, status=400)
    
    try:
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace(' ', '+'))
        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00').replace(' ', '+'))
    except (ValueError, TypeError): return JsonResponse({'error': 'Invalid date'}, status=400)
    
    # เช็คสิทธิ์ (ถ้าไม่ล็อกอิน = สาธารณะ)
    is_public_view = request.GET.get('public', 'false').lower() == 'true' or not request.user.is_authenticated
    
    # ✅ แสดงทั้ง APPROVED และ PENDING เพื่อให้เห็นว่าไม่ว่าง
    status_filter = ['APPROVED', 'PENDING']
    
    bookings = Booking.objects.filter(start_time__lt=end_dt, end_time__gt=start_dt, status__in=status_filter).select_related('room', 'user')
    if room_id: bookings = bookings.filter(room_id=room_id)
        
    events = []
    for b in bookings:
        event_title = b.title or "ไม่มีหัวข้อ"
        description = b.description or ""
        
        # ปรับแต่งการแสดงผลสำหรับ Public
        if is_public_view:
            description = "" # ซ่อนรายละเอียด
            if b.status == 'PENDING':
                 event_title = "⏳ รออนุมัติ"
            else:
                 event_title = "🔒 ไม่ว่าง" 

        events.append({
            'id': b.id, 
            'title': event_title, 
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(), 
            'resourceId': b.room.id,
            'extendedProps': { 
                'status': b.status,
                'description': description
            },
        })
    return JsonResponse(events, safe=False)

@login_required
@require_POST
def update_booking_time_api(request):
    pass
@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id):
    pass
@require_POST
def teams_action_receiver(request):
    pass
def _update_outlook_after_teams_action(booking):
    pass
def _update_teams_card_after_action(booking, new_status, action_type):
    pass

# ----------------------------------------------------------------------
# I. MANAGEMENT, REPORTS, EXPORT
# ----------------------------------------------------------------------
@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    pass
@login_required
@user_passes_test(is_admin)
def edit_user_roles_view(request, user_id):
    pass
@login_required
@user_passes_test(is_admin)
def room_management_view(request):
    pass
@login_required
@user_passes_test(is_admin)
def add_room_view(request):
    pass
@login_required
@user_passes_test(is_admin)
def edit_room_view(request, room_id):
    pass
@login_required
@user_passes_test(is_admin)
@require_POST
def delete_room_view(request, room_id):
    pass
@login_required
@user_passes_test(is_admin) 
def audit_log_view(request):
    pass
@login_required
@user_passes_test(is_admin)
def reports_view(request):
    pass
@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    pass
@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    pass