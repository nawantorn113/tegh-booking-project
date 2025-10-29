import json
import re # 1. เพิ่ม import นี้
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.models import User, Group
# --- DAL ---
try:
    from dal_select2.views import Select2QuerySetView
    DAL_AVAILABLE = True
except ImportError:
    DAL_AVAILABLE = False
    class Select2QuerySetView: pass
# --- End DAL ---
from django.core.mail import send_mail
from django.template.loader import render_to_string, get_template
from django.conf import settings
# --- openpyxl ---
try:
    from openpyxl import Workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
# --- WeasyPrint ---
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
# --- End Libs ---
from collections import defaultdict
from django.utils import timezone # 👈 (เพิ่มอันนี้)
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

# 2. แก้ไข Imports (ลบ Profile, Equipment, และ BookingFile)
from .models import Room, Booking, LoginHistory
from .forms import BookingForm, CustomPasswordChangeForm, RoomForm 
# (ลบ ProfileForm)


# --- Helper Functions ---
def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Admin').exists())
def is_approver_or_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=['Approver', 'Admin']).exists())

# (Login/Logout History ... Auth Views ... Email Functions ... Autocomplete ... เหมือนเดิม)
@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip_address = request.META.get('REMOTE_ADDR')
    LoginHistory.objects.create(user=user, action='LOGIN', ip_address=ip_address)
@receiver(user_logged_out)
def user_logged_out_callback(sender, request, user, **kwargs):
    if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
        ip_address = request.META.get('REMOTE_ADDR')
        try:
            LoginHistory.objects.create(user=user, action='LOGOUT', ip_address=ip_address)
        except Exception as e: print(f"Error creating logout history for {user.username}: {e}")
    elif user: print(f"Attempted to log logout for non-authenticated or invalid user: {user}")
def get_admin_emails(): return list(User.objects.filter(Q(groups__name__in=['Admin', 'Approver']) | Q(is_superuser=True), is_active=True).exclude(email__exact='').values_list('email', flat=True))
def send_booking_notification(booking, template_name, subject_prefix):
    recipients = get_admin_emails()
    if not recipients: print(f"Skipping email '{subject_prefix}': No recipients found."); return
    if not isinstance(recipients, list): recipients = [recipients]
    
    # (แก้ไข: สร้าง Subject ที่นี่)
    subject = f"[{subject_prefix}] การจองห้อง: {booking.title} ({booking.room.name})"
    
    context = {'booking': booking, 'settings': settings}
    try:
        message_html = render_to_string(template_name, context)
        if hasattr(settings, 'EMAIL_HOST') and settings.EMAIL_HOST:
            send_mail(subject, message_html, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=message_html)
            print(f"Email '{subject}' sent to: {', '.join(recipients)}")
        else: print(f"--- (Email Simulation) ---\nSubject: {subject}\nTo: {', '.join(recipients)}\n--- End Sim ---")
    except Exception as e: print(f"Error preparing/sending email '{subject}': {e}")
if DAL_AVAILABLE:
    class UserAutocomplete(Select2QuerySetView):
        def get_queryset(self):
            if not self.request.user.is_authenticated: return User.objects.none()
            qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
            if self.q: qs = qs.filter( Q(username__icontains=self.q) | Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q) | Q(email__icontains=self.q) )
            return qs[:15]
        def get_result_label(self, item): return f"{item.get_full_name() or item.username} ({item.email or 'No email'})"
else: 
    @login_required
    def UserAutocomplete(request): return JsonResponse({'error': 'Autocomplete unavailable.'}, status=501)
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
    user_before = request.user
    user_pk_before = user_before.pk
    logout(request)
    try:
        user_obj_for_signal = User.objects.get(pk=user_pk_before)
        user_logged_out.send(sender=user_obj_for_signal.__class__, request=request, user=user_obj_for_signal)
    except User.DoesNotExist: print(f"User with PK {user_pk_before} not found after logout, skipping history.")
    except Exception as e: print(f"Error sending user_logged_out signal for PK {user_pk_before}: {e}")
    messages.success(request, 'คุณได้ออกจากระบบเรียบร้อยแล้ว');
    return redirect('login')

# --- 3. START: เพิ่มฟังก์ชัน Smart Search (ใหม่) ---
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
        if now > end_time:
            start_time, end_time = None, None 
            
    elif "เช้านี้" in query_text:
        start_time = timezone.make_aware(datetime.combine(today, datetime.time(9, 0)))
        end_time = timezone.make_aware(datetime.combine(today, datetime.time(12, 0)))
        if now > end_time:
            start_time, end_time = None, None

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
        if now > end_time:
            start_time, end_time = None, None
            
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

    context = {
        'query_text': query_text,
        'search_params': search_params,
        'available_rooms': available_rooms.order_by('capacity'),
    }
    return render(request, 'pages/search_results.html', context)
# --- 3. END: เพิ่มฟังก์ชัน Smart Search ---


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
        current = room.bookings.filter(start_time__lte=now, end_time__gt=now, status='APPROVED').select_related('booked_by').first()
        room.status = 'ไม่ว่าง' if current else 'ว่าง'
        room.current_booking_info = current
        room.next_booking_info = None
        if not current:
            room.next_booking_info = room.bookings.filter(start_time__gt=now, status='APPROVED').select_related('booked_by').order_by('start_time').first()
        room.equipment_list = [eq.strip() for eq in (room.equipment_in_room or "").splitlines() if eq.strip()]
        buildings[room.building or "(ไม่ได้ระบุอาคาร)"].append(room)
    my_bookings_today_count = Booking.objects.filter(booked_by=request.user, start_time__date=now.date()).count()
    summary = {
        'total_rooms': Room.objects.count(),
        'today_bookings': Booking.objects.filter(start_time__date=now.date(), status='APPROVED').count(),
        'pending_approvals': Booking.objects.filter(status='PENDING').count(),
        'my_bookings_today': my_bookings_today_count,
    }
    context = {'buildings': dict(buildings), 'summary_cards': summary, 'current_sort': sort_by, 'all_rooms': all_rooms}
    return render(request, 'pages/dashboard.html', context)


@login_required
def room_calendar_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    form = BookingForm(initial={'room': room}) 
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
    context = {
        'my_bookings': bookings,
        'all_rooms': Room.objects.all().order_by('name'),
        'status_choices': Booking.STATUS_CHOICES,
        'current_date': date_f,
        'current_room': room_f,
        'current_status': status_f,
        
        # --- ⬇️ (แก้ไขตามคำขอ) ⬇️ ---
        'now_time': timezone.now()
    }
    return render(request, 'pages/history.html', context)

@login_required
def booking_detail_view(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related('room', 'booked_by')
                        .prefetch_related('participants'), # 4. ลบ 'equipment' และ 'files'
        pk=booking_id
    )
    is_participant = request.user in booking.participants.all()
    if (booking.booked_by != request.user and not is_admin(request.user) and not is_participant):
        messages.error(request, "คุณไม่มีสิทธิ์เข้าดูรายละเอียดการจองนี้");
        return redirect('dashboard')
    context = {'booking': booking}
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
    return render(request, 'pages/change_password.html', {
        'password_form': password_form
    })


# --- Admin ---
# (ลบ admin_dashboard_view)


# --- APIs ---
# (rooms_api, bookings_api, update_booking_time_api, delete_booking_api ... เหมือนเดิม)
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
        start_dt = timezone.make_aware(datetime.fromisoformat(start_str.replace('Z', '+00:00')))
        end_dt = timezone.make_aware(datetime.fromisoformat(end_str.replace('Z', '+00:00')))
    except (ValueError, TypeError): return JsonResponse({'error': 'Invalid date format.'}, status=400)
    bookings = Booking.objects.filter(start_time__lt=end_dt, end_time__gt=start_dt).select_related('room', 'booked_by')
    if room_id:
        try: bookings = bookings.filter(room_id=int(room_id))
        except (ValueError, TypeError): return JsonResponse({'error': 'Invalid room ID.'}, status=400)
    events = []
    for b in bookings:
        events.append({
            'id': b.id, 'title': b.title, 'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(), 'resourceId': b.room.id,
            'extendedProps': { 'room_id': b.room.id, 'room_name': b.room.name, 'booked_by_username': b.booked_by.username, 'status': b.status, 'user_id': b.booked_by.id },
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
        if booking.booked_by != request.user and not is_admin(request.user): return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        try:
            new_start = timezone.make_aware(datetime.fromisoformat(start_str.replace('Z', '+00:00')))
            new_end = timezone.make_aware(datetime.fromisoformat(end_str.replace('Z', '+00:00')))
        except ValueError: return JsonResponse({'status': 'error', 'message': 'Invalid date format.'}, status=400)
        if new_end <= new_start: return JsonResponse({'status': 'error', 'message': 'End time must be after start time.'}, status=400)
        conflicts = Booking.objects.filter( room=booking.room, start_time__lt=new_end, end_time__gt=new_start).exclude(pk=booking.id).exclude(status__in=['REJECTED', 'CANCELLED'])
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
        if booking.booked_by != request.user and not is_admin(request.user): return JsonResponse({'success': False, 'error': 'ไม่มีสิทธิ์ยกเลิก'}, status=403)
        if booking.status in ['CANCELLED', 'REJECTED']: return JsonResponse({'success': False, 'error': 'การจองนี้ถูกยกเลิกหรือปฏิเสธไปแล้ว'})
        booking.status = 'CANCELLED'
        booking.save()
        return JsonResponse({'success': True, 'message': 'ยกเลิกการจองเรียบร้อย'})
    except Booking.DoesNotExist: return JsonResponse({'success': False, 'error': 'ไม่พบการจองนี้'}, status=44)
    except Exception as e:
        print(f"Error in delete_booking_api for booking {booking_id}: {e}")
        return JsonResponse({'success': False, 'error': 'เกิดข้อผิดพลาดบนเซิร์ฟเวอร์'}, status=500)

# --- 5. START: แก้ไข create_booking_view (ลบ user=... และ equipment) ---
@login_required
@require_POST
def create_booking_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    form = BookingForm(request.POST, request.FILES) 
    
    # (ลบ Logic ของ 'attachments' (หลายไฟล์) ออก)
    # uploaded_files = request.FILES.getlist('attachments')

    if form.is_valid():
        
        # (ลบ Check 8 ไฟล์)
            
        try:
            booking = form.save(commit=False)
            booking.room = room
            booking.booked_by = request.user
            
            booking.clean() 

            participant_count = form.cleaned_data.get('participant_count', 1)
            if participant_count >= 15:
                booking.status = 'PENDING'
                messages.success(request, f"จอง '{booking.title}' ({room.name}) เรียบร้อย **รออนุมัติ**")
            else:
                booking.status = 'APPROVED'
                messages.success(request, f"จอง '{booking.title}' ({room.name}) **อนุมัติอัตโนมัติ**")
            
            booking.save() 
            form.save_m2m() # (บันทึก participants)
            
            # (ลบ Logic การ save หลายไฟล์)
            
            if booking.status == 'PENDING':
                send_booking_notification(booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ')
            else:
                send_booking_notification(booking, 'emails/new_booking_approved.html', 'จองสำเร็จ')

            return redirect('room_calendar', room_id=room.id)

        except ValidationError as e:
            error_str = ", ".join(e.messages)
            messages.error(request, f"ไม่สามารถสร้างการจองได้: {error_str}")
            context = {'room': room, 'form': form}
            return render(request, 'pages/room_calendar.html', context)
            
    else: # Form invalid
        error_list = []
        for field, errors in form.errors.items():
            field_label = form.fields.get(field).label if field != '__all__' and field in form.fields else (field if field != '__all__' else 'Form')
            error_list.append(f"{field_label}: {', '.join(errors)}")
        error_str = "; ".join(error_list)
        messages.error(request, f"ไม่สามารถสร้างการจองได้: {error_str}")
        context = {'room': room, 'form': form}
        return render(request, 'pages/room_calendar.html', context)
# --- 5. END: แก้ไข create_booking_view ---


# --- 6. START: แก้ไข edit_booking_view (ลบ user=... และ equipment) ---
@login_required
def edit_booking_view(request, booking_id):
    # 6.1 ลบ prefetch_related('files') ออก
    booking = get_object_or_404(Booking, pk=booking_id)
    
    if booking.booked_by != request.user and not is_admin(request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขการจองนี้")
        return redirect('history')

    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES, instance=booking) # 6.2 ลบ user=...
        
        # (ลบ Logic การดึงไฟล์)
        
        if form.is_valid():
            
            # (ลบ Logic การนับไฟล์)
            
            try:
                updated_booking = form.save(commit=False)
                updated_booking.clean() 

                new_count = form.cleaned_data.get('participant_count', 1)
                changed_for_approval = any(f in form.changed_data for f in ['start_time', 'end_time', 'participant_count'])
                
                if new_count >= 15 and changed_for_approval and updated_booking.status not in ['PENDING', 'REJECTED', 'CANCELLED']:
                       updated_booking.status = 'PENDING'
                       messages.info(request, "การแก้ไขต้องรอการอนุมัติใหม่")
                
                updated_booking.save()
                form.save_m2m() # (บันทึก participants)
                
                # (ลบ Logic การ save หลายไฟล์)
                
                messages.success(request, "แก้ไขข้อมูลการจองเรียบร้อยแล้ว")

                if updated_booking.status == 'PENDING' and changed_for_approval:
                       send_booking_notification(updated_booking, 'emails/new_booking_pending.html', 'โปรดอนุมัติ (แก้ไข)')

                return redirect('history')

            except ValidationError as e:
                error_str = ", ".join(e.messages)
                form.add_error(None, e)
                messages.error(request, f"ไม่สามารถบันทึกได้: {error_str}")

        else: 
             messages.error(request, "ไม่สามารถบันทึกการแก้ไขได้ กรุณาตรวจสอบข้อผิดพลาด")
    else: 
        form = BookingForm(instance=booking) # 6.3 ลบ user=...

    return render(request, 'pages/edit_booking.html', {'form': form, 'booking': booking})
# --- 6. END: แก้ไข edit_booking_view ---


@login_required
@require_POST
def delete_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if booking.booked_by != request.user and not is_admin(request.user):
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
                                       .select_related('room', 'booked_by') \
                                       .order_by('start_time')
    return render(request, 'pages/approvals.html', {'pending_bookings': pending_bookings})

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('booked_by'), id=booking_id, status='PENDING')
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"อนุมัติการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')

@login_required
@user_passes_test(is_approver_or_admin)
@require_POST
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('booked_by'), id=booking_id, status='PENDING')
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"ปฏิเสธการจอง '{booking.title}' เรียบร้อย")
    return redirect('approvals')


# --- Management ---
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
        selected_group_ids = request.POST.getlist('groups')
        selected_groups = Group.objects.filter(pk__in=selected_group_ids)
        user_to_edit.groups.set(selected_groups)
        user_to_edit.is_staff = (is_admin(user_to_edit) or user_to_edit.is_superuser)
        user_to_edit.save()
        messages.success(request, f"อัปเดตสิทธิ์ผู้ใช้ '{user_to_edit.username}' เรียบร้อย")
        return redirect('user_management')
    context = {
        'user_to_edit': user_to_edit,
        'all_groups': all_groups,
        'user_group_pks': list(user_to_edit.groups.values_list('pk', flat=True))
     }
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
        if form.is_valid():
            form.save()
            messages.success(request, "เพิ่มห้องประชุมใหม่เรียบร้อย")
            return redirect('rooms')
        else:
             messages.error(request, "ไม่สามารถเพิ่มห้องได้ กรุณาตรวจสอบข้อผิดพลาด")
    else: 
        form = RoomForm()
    return render(request, 'pages/room_form.html', {'form': form, 'title': 'เพิ่มห้องประชุมใหม่'})

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
    return render(request, 'pages/room_form.html', {'form': form, 'title': f'แก้ไขข้อมูลห้อง: {room.name}'})

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

    context = {
        'room_usage_stats': room_usage_stats, 
        'report_title': report_title,
        'all_departments': departments_dropdown, 
        'current_period': period,
        'current_department': department,
        'room_usage_labels': json.dumps(room_usage_labels),
        'room_usage_data': json.dumps(room_usage_data),
        'dept_usage_labels': json.dumps(dept_usage_labels),
        'dept_usage_data': json.dumps(dept_usage_data),
        'pending_count': Booking.objects.filter(status='PENDING').count(),
        'today_bookings_count': Booking.objects.filter(start_time__date=timezone.now().date(), status='APPROVED').count(),
        'total_users_count': User.objects.count(),
        'total_rooms_count': Room.objects.count(),
        'login_history': LoginHistory.objects.select_related('user').order_by('-timestamp')[:7],
     }
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
    ).select_related('room', 'booked_by').order_by('start_time')

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
            b.id, b.title, b.room.name, b.booked_by.get_full_name() or b.booked_by.username,
            b.department,
            b.start_time.strftime('%Y-%m-%d %H:%M'),
            b.end_time.strftime('%Y-%m-%d %H:%M'),
            b.participant_count
        ])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=booking_report_{today}.xlsx'
    wb.save(response)
    return response

# ... (โค้ด export_reports_excel) ...
    wb.save(response)
    return response

# --- ⬇️ เพิ่มฟังก์ชันนี้เข้าไป ⬇️ ---
@login_required
@user_passes_test(is_admin)
def export_reports_pdf(request):
    # (โค้ดสำหรับสร้าง PDF ยังไม่ได้เขียน)
    # เราใส่แค่หน้าเปล่าๆ ไว้ก่อนเพื่อไม่ให้ Error
    messages.error(request, "ฟังก์ชัน Export PDF ยังไม่พร้อมใช้งาน")
    return redirect('reports')

# (เพิ่มโค้ด PDF ที่นี่ ถ้าคุณต้องการ)