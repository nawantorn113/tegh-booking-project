import json
import re
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.models import User, Group

from dal_select2.views import Select2QuerySetView
DAL_AVAILABLE = True 

from django.core.mail import send_mail
from django.template.loader import render_to_string, get_template
from django.conf import settings
try:
    from openpyxl import Workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
from collections import defaultdict
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from django.db import transaction 
from dateutil.relativedelta import relativedelta 

from .models import Room, Booking
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm

# --- Helper Functions ---
def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists())
def is_approver_or_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=['Approver', 'Admin']).exists())

# --- Context Function (สำหรับ Navbar) ---
def get_base_context(request):
    current_url_name = request.resolver_match.url_name if request.resolver_match else ''
    is_admin_user = is_admin(request.user)
    
    menu_structure = [
        {'label': 'หน้าหลัก', 'url_name': 'dashboard', 'icon': 'bi-house-fill', 'show': True},
        {'label': 'ปฏิทินรวม', 'url_name': 'master_calendar', 'icon': 'bi-calendar3-range', 'show': True},
        {'label': 'ประวัติการจอง', 'url_name': 'history', 'icon': 'bi-clock-history', 'show': True},
        {'label': 'รออนุมัติ', 'url_name': 'approvals', 'icon': 'bi-check2-circle', 'show': is_admin_user},
    ]
    
    admin_menu_structure = [
        {'label': 'จัดการห้องประชุม', 'url_name': 'rooms', 'icon': 'bi-door-open-fill', 'show': is_admin_user},
        {'label': 'จัดการผู้ใช้งาน', 'url_name': 'user_management', 'icon': 'bi-people-fill', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'url_name': 'reports', 'icon': 'bi-bar-chart-fill', 'show': is_admin_user},
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
    if is_admin_user:
        pending_bookings = Booking.objects.filter(status='PENDING').order_by('-created_at')
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

# --- Callbacks / Email / Autocomplete ---
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    pass 
@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    pass 
def get_admin_emails(): return list(User.objects.filter(Q(groups__name__in=['Admin', 'Approver']) | Q(is_superuser=True), is_active=True).exclude(email__exact='').values_list('email', flat=True))
def send_booking_notification(booking, template_name, subject_prefix):
    recipients = get_admin_emails()
    if not recipients: print(f"Skipping email '{subject_prefix}': No recipients found."); return
    if not isinstance(recipients, list): recipients = [recipients]
    subject = f"[{subject_prefix}] การจองห้อง: {booking.title} ({booking.room.name})"
    context = {'booking': booking, 'settings': settings}
    try:
        message_html = render_to_string(template_name, context)
        if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
            send_mail(subject, message_html, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=message_html)
            print(f"Email '{subject}' sent to: {', '.join(recipients)}")
        else: print(f"--- (Email Simulation) ---\nSubject: {subject}\nTo: {', '.join(recipients)}\n--- End Sim ---")
    except Exception as e: print(f"Error preparing/sending email '{subject}': {e}")


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
            next_url = request.GET.get('next', 'dashboard'); messages.success(request, f'ยินดีต้อนรับ, {user.get_full_name() or user.username}!')
            return redirect(next_url)
        else:
            if '__all__' in form.errors: messages.error(request, form.errors['__all__'][0])
            else: messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง โปรดลองอีกครั้ง')
    else: form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว');
    return redirect('login') 

# --- Smart Search ---
def parse_search_query(query_text):
    capacity = None
    start_time = None
    end_time = None
    now = timezone.now()
    today = now.date()
    capacity_match = re.search(r'(\d+)\s*คน', query_text)
    if capacity_match:
        capacity = int(capacity_match.group(1))
    if "บ่ายนี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, datetime.time(13, 0)))
        end_time = timezone.make_aware(datetime.combine(today, datetime.time(17, 0)))
        if now > end_time: start_time, end_time = None, None 
    elif "เช้านี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, datetime.time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, datetime.time(12, 0)))
        if now > end_time: start_time, end_time = None, None
    elif "พรุ่งนี้เช้า" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(12, 0)))
    elif "พรุ่งนี้บ่าย" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(13, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(17, 0)))
    elif "พรุ่งนี้" in query_text:
        tomorrow = today + timedelta(days=1)
        start_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(tomorrow, datetime.time(17, 0)))
    elif "วันนี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, datetime.time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, datetime.time(17, 0)))
        if now > end_time: start_time, end_time = None, None
    return capacity, start_time, end_time
@login_required
def smart_search_view(request):
    query_text = request.GET.get('q', '')
    available_rooms = Room.objects.all()
    search_params = {}
    if not query_text:
        available_rooms = Room.objects.none()
    else:
        capacity, start_time, end_time = parse_search_query(query_text)
        search_params['capacity'] = capacity
        search_params['start_time'] = start_time
        search_params['end_time'] = end_time
        if capacity:
            available_rooms = available_rooms.filter(capacity__gte=capacity)
        if start_time and end_time:
            conflicting_room_ids = Booking.objects.filter(
                status__in=['APPROVED', 'PENDING'],
                start_time__lt=end_time,
                end_time__gt=start_time
            ).values_list('room_id', flat=True).distinct()
            available_rooms = available_rooms.exclude(id__in=conflicting_room_ids)
    
    context = get_base_context(request)
    context.update({
        'query_text': query_text,
        'search_params': search_params,
        'available_rooms': available_rooms.order_by('capacity'),
    })
    return render(request, 'pages/search_results.html', context)

# --- Main Pages ---
@login_required
def dashboard_view(request):
    now = timezone.now(); sort_by = request.GET.get('sort', 'floor')
    all_rooms = Room.objects.all()
    if sort_by == 'status':
        all_rooms = sorted(all_rooms, key=lambda r: not r.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').exists())
    elif sort_by == 'capacity':
         all_rooms = sorted(all_rooms, key=lambda r: r.capacity, reverse=True)
    elif sort_by == 'name':
        all_rooms = all_rooms.order_by('name')
    else: 
        all_rooms = all_rooms.order_by('building', 'floor', 'name')
    buildings = defaultdict(list)
    for room in all_rooms:
        current = room.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').select_related('user').first()
        room.status = 'ไม่ว่าง' if current else 'ว่าง'
        room.current_booking_info = current
        room.next_booking_info = None
        if not current:
            room.next_booking_info = room.bookings.filter(start_time__gt=now, status='APPROVED').select_related('user').order_by('start_time').first()
        
        buildings[room.building or "(ไม่ได้ระบุอาคาร)"].append(room)
        
    my_bookings_today_count = Booking.objects.filter(user=request.user, start_time__date=now.date()).count()
    
    context = get_base_context(request)
    
    summary = {
        'total_rooms': Room.objects.count(),
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': context['pending_count'], 
        'my_bookings_today': my_bookings_today_count,
    }
    
    context.update({
        'buildings': dict(buildings), 
        'summary_cards': summary, 
        'current_sort': sort_by, 
        'all_rooms': all_rooms,
    })
    return render(request, 'pages/dashboard.html', context)

@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
    else:
        form = BookingForm(initial={'room': room}) 
    
    context = get_base_context(request)
    context.update({
        'room': room, 
        'form': form
    })
    return render(request, 'pages/room_calendar.html', context)

@login_required
def master_calendar_view(request):
    context = get_base_context(request)
    return render(request, 'pages/master_calendar.html', context)

# --- 💡💡💡 [นี่คือจุดที่แก้ไข] 💡💡💡 ---
@login_required
def history_view(request):
    
    # 1. เช็ค Admin
    if is_admin(request.user):
        bookings = Booking.objects.all().select_related('room', 'user').order_by('-start_time')
    else:
        bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-start_time')

    # 2. (แก้ไข) เพิ่ม 'q_f' (Query Filter)
    date_f = request.GET.get('date')
    room_f = request.GET.get('room')
    status_f = request.GET.get('status')
    q_f = request.GET.get('q', '') # (รับคำค้นหา)

    if date_f:
        try:
            bookings = bookings.filter(start_time__date=datetime.strptime(date_f, '%Y-%m-%d').date())
        except ValueError:
            messages.warning(request, "รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD")
            date_f = None
    if room_f:
        try:
            room_id_int = int(room_f)
            bookings = bookings.filter(room_id=room_id_int)
        except (ValueError, TypeError):
             messages.warning(request, "Room ID ไม่ถูกต้อง")
             room_f = None
    if status_f and status_f in dict(Booking.STATUS_CHOICES):
        bookings = bookings.filter(status=status_f)
    elif status_f:
        messages.warning(request, "สถานะการจองไม่ถูกต้อง")
        status_f = None
    
    # (เพิ่ม Logic การค้นหา)
    if q_f:
        bookings = bookings.filter(
            Q(title__icontains=q_f) |
            Q(user__username__icontains=q_f) |
            Q(user__first_name__icontains=q_f) |
            Q(user__last_name__icontains=q_f) |
            Q(department__icontains=q_f) |
            # (เพิ่มการค้นหา "รายชื่อผู้เข้าร่วม")
            Q(participants__username__icontains=q_f) |
            Q(participants__first_name__icontains=q_f) |
            Q(participants__last_name__icontains=q_f)
        ).distinct() # (distinct() จำเป็นมาก)

    # 3. (ส่ง Context ไปที่ Template)
    context = get_base_context(request)
    context.update({
        'bookings_list': bookings, 
        'all_rooms': Room.objects.all().order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
        'current_date': date_f,
        'current_room': room_f,
        'current_status': status_f,
        'current_query': q_f, # (ส่งคำค้นหากลับไปที่ Template)
        'now_time': timezone.now()
    })
    return render(request, 'pages/history.html', context)
# --- 💡💡💡 [สิ้นสุดการแก้ไข] 💡💡💡 ---

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('room', 'user')
                          .prefetch_related('participants'), 
        pk=booking_id
    )
    is_participant = request.user in booking.participants.all()
    if (booking.user != request.user and not is_admin(request.user) and not is_participant):
        messages.error(request, "คุณไม่มีสิทธิ์เข้าดูรายละเอียดการจองนี้");
        return redirect('dashboard')
        
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
            messages.success(request, 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว');
            return redirect('change_password')
        else:
            messages.error(request, 'ไม่สามารถเปลี่ยนรหัสผ่านได้ กรุณาตรวจสอบข้อผิดพลาด')
    else: 
        password_form = CustomPasswordChangeForm(request.user)
    
    context = get_base_context(request)
    context.update({'password_form': password_form})
    return render(request, 'pages/change_password.html', context)

# --- APIs ---
@login_required
def rooms_api(request):
    rooms = Room.objects.all().order_by('building', 'name')
    resources = [{'id': r.id, 'title': r.name, 'building': r.building or ""} for r in rooms]
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
    ).select_related('room', 'user')
    
    if room_id:
        try: bookings = bookings.filter(room_id=int(room_id))
        except (ValueError, TypeError): return JsonResponse({'error': 'Invalid room ID.'}, status=400)
    
    events = []
    for b in bookings:
        events.append({
            'id': b.id, 
            'title': b.title, 
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(), 
            'resourceId': b.room.id,
            'extendedProps': { 
                'room_id': b.room.id, 
                'room_name': b.room.name, 
                'booked_by_username': b.user.username if b.user else 'N/A',
                'status': b.status, 
                'user_id': b.user.id if b.user else None
            },
        })
    return JsonResponse(events, safe=False)
@login_required
@require_POST
def update_booking_time_api(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id'); start_str = data.get('start_time'); end_str = data.get('end_time')
        if not all([booking_id, start_str, end_str]): return JsonResponse({'status': 'error', 'message': 'Missing required data.'}, status=400)
        booking = get_object_or_404(Booking, pk=booking_id)
        if booking.user != request.user and not is_admin(request.user): return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        try:
            new_start = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace(' ', '+'))
            new_end = datetime.fromisoformat(end_str.replace('Z', '+00:00').replace(' ', '+'))
        except ValueError: return JsonResponse({'status': 'error', 'message': 'Invalid date format.'}, status=400)
        if new_end <= new_start: return JsonResponse({'status': 'error', 'message': 'End time must be after start time.'}, status=400)
        
        conflicts = Booking.objects.filter( 
            room=booking.room, 
            start_time__lt=new_end, 
            end_time__gt=new_start,
            status__in=['APPROVED', 'PENDING']
        ).exclude(pk=booking.id)
        
        if conflicts.exists(): return JsonResponse({'status': 'error', 'message': 'เลือกช่วงเวลาใหม่ไม่ได้ เนื่องจากเวลาทับซ้อนกับการจองอื่น'}, status=400)
        
        booking.start_time = new_start
        booking.end_time = new_end
        status_message = "Booking time updated successfully."
        if booking.participant_count >= 15 and booking.status not in ['PENDING', 'REJECTED', 'CANCELLED']:
             booking.status = 'PENDING'
             status_message = "Booking time updated. Approval now required."
        booking.save()
        return JsonResponse({'status': 'success', 'message': status_message, 'new_status': booking.status})
    except json.JSONDecodeError: return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
    except Booking.DoesNotExist: return JsonResponse({'status': 'error', 'message': 'Booking not found.'}, status=404)
    except Exception as e:
        print(f"Error in update_booking_time_api: {e}")
        return JsonResponse({'status': 'error', 'message': 'Server error.'}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_booking_api(request, booking_id):
    try:
        booking = get_object_or_404(Booking, pk=booking_id)
        if booking.user != request.user and not is_admin(request.user): return JsonResponse({'success': False, 'error': 'ไม่มีสิทธิ์ยกเลิก'}, status=403)
        if booking.status in ['CANCELLED', 'REJECTED']: return JsonResponse({'success': False, 'error': 'การจองนี้ถูกยกเลิกหรือปฏิเสธไปแล้ว'})
        booking.status = 'CANCELLED'
        booking.save()
        return JsonResponse({'success': True, 'message': 'ยกเลิกการจองเรียบร้อย'})
    except Booking.DoesNotExist: return JsonResponse({'success': False, 'error': 'ไม่พบการจองนี้'}, status=44)
    except Exception as e:
        print(f"Error in delete_booking_api for booking {booking_id}: {e}")
        return JsonResponse({'success': False, 'error': 'เกิดข้อผิดพลาดบนเซิร์ฟเวอร์'}, status=500)

# --- Booking Views ---
@login_required
@require_POST
@transaction.atomic 
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
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
                messages.error(request, "ไม่สามารถจองได้: ช่วงเวลาที่คุณเลือกทับซ้อนกับการจองอื่น")
                context = get_base_context(request)
                context.update({'room': room, 'form': form})
                return render(request, 'pages/room_calendar.html', context)
            
            parent_booking.save()
            form.save_m2m() 

            if recurrence and recurrence != 'NONE':
                
                parent_booking.recurrence_rule = recurrence 
                parent_booking.save()
                
                next_start_time = start_time
                next_end_time = end_time
                bookings_to_create = []

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
                        bookings_to_create.append(new_booking)
                    else:
                        print(f"Skipping recurring booking on {next_start_time.date()} due to conflict.")

                created_bookings = Booking.objects.bulk_create(bookings_to_create)
                
                participants = list(parent_booking.participants.all())
                for booking in created_bookings:
                    booking.participants.set(participants)

            if new_status == 'PENDING':
                send_booking_notification(parent_booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ')
                messages.success(request, f"จอง '{parent_booking.title}' ({room.name}) เรียบร้อย **รออนุมัติ**")
            else:
                send_booking_notification(parent_booking, 'emails/new_booking_approved.html', 'จองสำเร็จ')
                messages.success(request, f"จอง '{parent_booking.title}' ({room.name}) **อนุมัติอัตโนมัติ**")
            
            return HttpResponse(
                '<script>window.parent.location.reload();</script>',
                status=200
            )

        except ValidationError as e:
            error_str = ", ".join(e.messages)
            messages.error(request, f"ไม่สามารถสร้างการจองได้: {error_str}")
    
    error_list = []
    for field, errors in form.errors.items():
        field_label = form.fields.get(field).label if field != '__all__' and field in form.fields else (field if field != '__all__' else 'Form')
        error_list.append(f"{field_label}: {', '.join(errors)}")
    error_str = "; ".join(error_list)
    messages.error(request, f"ไม่สามารถสร้างการจองได้: {error_str}")
    
    context = get_base_context(request)
    context.update({'room': room, 'form': form})
    return render(request, 'pages/room_calendar.html', context)

@login_required
def edit_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.user != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขการจองนี้")
        return redirect('history')
        
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking)
        if form.is_valid():
            try:
                updated_booking = form.save(commit=False)
                updated_booking.clean() 
                new_count = form.cleaned_data.get('participant_count', 1)
                changed_for_approval = any(f in form.changed_data for f in ['start_time', 'end_time', 'participant_count'])
                if new_count >= 15 and changed_for_approval and updated_booking.status not in ['PENDING', 'REJECTED', 'CANCELLED']:
                        updated_booking.status = 'PENDING'
                        messages.info(request, "การแก้ไขต้องรอการอนุมัติใหม่")
                updated_booking.save()
                form.save_m2m() 
                messages.success(request, "แก้ไขข้อมูลการจองเรียบร้อยแล้ว")
                if updated_booking.status == 'PENDING' and changed_for_approval:
                        send_booking_notification(updated_booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ (แก้ไข)')
                return redirect('history')
            except ValidationError as e:
                error_str = ", ".join(e.messages)
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
    if booking.user != request.user and not is_admin(request.user):
        messages.error(request, "ไม่มีสิทธิ์ยกเลิกการจองนี้")
        return redirect('history')
    if booking.status in ['CANCELLED', 'REJECTED']:
        messages.warning(request, "การจองนี้ถูกยกเลิกหรือปฏิเสธไปแล้ว")
        return redirect('history')
    booking.status = 'CANCELLED'
    booking.save()
    messages.success(request, f"ยกเลิกการจอง '{booking.title}' เรียบร้อย")
    return redirect('history')

# --- Approvals ---
@login_required
@user_passes_test(is_approver_or_admin)
def approvals_view(request):
    pending_bookings = Booking.objects.filter(status='PENDING') \
                                        .select_related('room', 'user') \
                                        .order_by('start_time')
    context = get_base_context(request)
    context.update({'pending_bookings': pending_bookings})
    return render(request, 'pages/approvals.html', context)
@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('user'), id=booking_id, status='PENDING')
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"อนุมัติการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')
@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('user'), id=booking_id, status='PENDING')
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"ปฏิเสธการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')

# --- Management ---
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
            messages.success(request, "เพิ่มห้องประชุมใหม่เรียบร้อย")
            return redirect('rooms')
        else:
            messages.error(request, "ไม่สามารถเพิ่มห้องได้ กรุณาตรวจสอบข้อผิดพลาด")
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

# --- Reports ---
@login_required
@user_passes_test(is_admin)
def reports_view(request):
    period = request.GET.get('period', 'monthly')
    department = request.GET.get('department', '')
    today = timezone.now().date()
    start_date = today
    if period == 'daily':
        start_date = today
        report_title = f'รายงานการใช้งานรายวัน ({today:%d %b %Y})'
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
        report_title = f'รายงานการใช้งานรายสัปดาห์ ({start_date:%d %b} - {today:%d %b %Y})'
    else:
        period = 'monthly'
        start_date = today - timedelta(days=29)
        report_title = f'รายงานการใช้งานรายเดือน ({start_date:%d %b} - {today:%d %b %Y})'
    recent_bookings = Booking.objects.filter(
        start_time__date__gte=start_date,
        start_time__date__lte=today,
        status='APPROVED'
    )
    if department:
        recent_bookings = recent_bookings.filter(department=department)
        report_title += f" (แผนก: {department})"
    room_usage_stats = Room.objects.annotate(
        booking_count=Count('bookings', filter=Q(bookings__in=recent_bookings))
    ).filter(booking_count__gt=0).order_by('-booking_count')
    room_usage_labels = [r.name for r in room_usage_stats[:10]]
    room_usage_data = [r.booking_count for r in room_usage_stats[:10]]
    dept_usage_query = recent_bookings.exclude(department__exact='').exclude(department__isnull=True) \
                                        .values('department') \
                                        .annotate(count=Count('id')) \
                                        .order_by('-count')
    dept_usage_labels = [d['department'] for d in dept_usage_query[:10] if d.get('department')]
    dept_usage_data = [d['count'] for d in dept_usage_query[:10] if d.get('department')]
    departments_dropdown = Booking.objects.exclude(department__exact='').exclude(department__isnull=True) \
                                        .values_list('department', flat=True) \
                                        .distinct().order_by('department')
    
    context = get_base_context(request)
    context.update({
        'room_usage_stats': room_usage_stats, 
        'report_title': report_title,
        'all_departments': departments_dropdown, 
        'current_period': period,
        'current_department': department,
        'room_usage_labels': json.dumps(room_usage_labels),
        'room_usage_data': json.dumps(room_usage_data),
        'dept_usage_labels': json.dumps(dept_usage_labels),
        'dept_usage_data': json.dumps(dept_usage_data),
        'pending_count': context['pending_count'],
        'today_bookings_count': Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count(),
        'total_users_count': User.objects.count(),
        'total_rooms_count': Room.objects.count(),
        'login_history': [], 
     })
    return render(request, 'pages/reports.html', context)
@login_required
@user_passes_test(is_admin)
def export_reports_excel(request):
    if not OPENPYXL_AVAILABLE:
        messages.error(request, "ไม่สามารถส่งออกเป็น Excel ได้: ไม่ได้ติดตั้งไลบรารี openpyxl")
        return redirect('reports')
    period = request.GET.get('period', 'monthly'); department = request.GET.get('department', '')
    today = timezone.now().date()
    start_date = today
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
    else:
        period = 'monthly'
        start_date = today - timedelta(days=29)
    bookings = Booking.objects.filter(
        start_time__date__gte=start_date,
        start_time__date__lte=today,
        status='APPROVED'
    ).select_related('room', 'user').order_by('start_time')
    if department:
        bookings = bookings.filter(department=department)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Report {start_date} to {today}"
    headers = [
        "ID", "Title", "Room", "Booked By", "Department", 
        "Start Time", "End Time", "Participants"
    ]
    ws.append(headers)
    for b in bookings:
        ws.append([
            b.id, b.title, b.room.name, b.user.get_full_name() or b.user.username,
            b.department,
            b.start_time.strftime('%Y-%m-%d %H:%M'),
            b.end_time.strftime('%Y-%m-%d %H:%M'),
            b.participant_count
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=booking_report_{today}.xlsx'
    wb.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    messages.error(request, "ฟังก์ชัน Export PDF ยังไม่พร้อมใช้งาน")
    return redirect('reports')