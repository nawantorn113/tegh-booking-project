# booking/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.conf import settings
from .models import Booking, Room
from .forms import BookingForm
from datetime import timedelta
import requests
import json

# --- ส่วนของการแจ้งเตือน (Notification) ---
# [แนะนำ] ควรย้าย Token ไปเก็บใน settings.py หรือ Environment Variables ในอนาคต
LINE_TOKEN = 'YOUR_LINE_NOTIFY_TOKEN' # <-- อย่าลืมเปลี่ยนเป็น Token ของคุณ

def send_line_notify(message):
    if not LINE_TOKEN or LINE_TOKEN == 'YOUR_LINE_NOTIFY_TOKEN':
        print("LINE Notify is not configured.")
        return
    try:
        headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
        payload = {"message": message}
        requests.post("https://notify-api.line.me/api/notify", headers=headers, data=payload, timeout=5)
    except Exception as e:
        print(f"Error sending LINE Notify: {e}")

# --- Views พื้นฐาน ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
            return redirect('login')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')
    
# --- View หลักของระบบ ---
@login_required
def dashboard_view(request):
    my_bookings = Booking.objects.filter(booked_by=request.user).order_by('-start_time')
    rooms = Room.objects.all().order_by('name')
    is_admin = request.user.groups.filter(name='Admin').exists()
    is_approver = request.user.groups.filter(name='Approver').exists()
    context = {
        'my_bookings': my_bookings,
        'rooms': rooms,
        'is_admin': is_admin,
        'is_approver': is_approver,
    }
    if is_admin or is_approver:
        context['pending_bookings'] = Booking.objects.filter(status='PENDING')
    return render(request, 'dashboard.html', context)

@login_required
def bookings_api_view(request):
    bookings = Booking.objects.all()
    events = []
    for b in bookings:
        color = '#198754' if b.status=='APPROVED' else '#ffc107' if b.status=='PENDING' else '#dc3545'
        events.append({
            'id': b.id,
            'title': f"{b.title}\n({b.booked_by.username})",
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(),
            'resourceId': b.room.id,
            'color': color,
        })
    return JsonResponse(events, safe=False)

@login_required
def create_booking_view(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            # ตรวจสอบ recurring จาก form ถ้ามี
            recurring_type = request.POST.get('recurring', 'NONE') 
            booking.recurring = recurring_type
            booking.save()
            
            messages.success(request, f"การจองห้อง '{booking.room.name}' สำเร็จแล้ว")
            send_line_notify(f"จองห้อง: {booking.room.name}\nหัวข้อ: {booking.title}\nโดย: {booking.booked_by.username}\nสถานะ: {booking.get_status_display()}")

            # สร้างการจองซ้ำ (ถ้ามี)
            if recurring_type != 'NONE':
                occurrences = 4 
                for i in range(1, occurrences + 1):
                    if recurring_type == 'DAILY': delta = timedelta(days=i)
                    elif recurring_type == 'WEEKLY': delta = timedelta(weeks=i)
                    else: delta = timedelta(days=30*i)

                    Booking.objects.create(
                        room=booking.room,
                        booked_by=request.user,
                        title=booking.title,
                        start_time=booking.start_time + delta,
                        end_time=booking.end_time + delta,
                        recurring='NONE'
                    )
            return redirect('dashboard')
    else:
        form = BookingForm()
    return render(request, 'create_booking.html', {'form': form})

# --- Views สำหรับการอนุมัติ และ แก้ไข ---
def is_approver_or_admin(user):
    return user.groups.filter(name__in=['Approver', 'Admin']).exists()

@login_required
@user_passes_test(is_approver_or_admin)
def approve_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'APPROVED'
    booking.save()
    messages.success(request, f"การจอง '{booking.title}' ได้รับการอนุมัติแล้ว")
    return redirect('dashboard')

@login_required
@user_passes_test(is_approver_or_admin)
def reject_booking_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'REJECTED'
    booking.save()
    messages.warning(request, f"การจอง '{booking.title}' ถูกปฏิเสธ")
    return redirect('dashboard')

@login_required
def update_booking_time_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    # เพิ่มเงื่อนไขความปลอดภัย: แก้ไขได้เฉพาะเจ้าของ หรือ Admin
    if booking.booked_by != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            booking.start_time = parse_datetime(data['start'])
            booking.end_time = parse_datetime(data['end'])
            booking.save()
            return JsonResponse({'status': 'success', 'message': 'อัปเดตเวลาเรียบร้อยแล้ว'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)