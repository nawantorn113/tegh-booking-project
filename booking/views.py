from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils.dateparse import parse_datetime
from .models import Room, Booking

# --- ส่วนของการ Login/Logout ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('calendar')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('calendar')
        else:
            messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
            return redirect('login')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# --- ส่วนของหน้าปฏิทิน ---
@login_required
def calendar_view(request):
    rooms = Room.objects.all()
    return render(request, 'calendar.html', {'rooms': rooms})

@login_required
def create_booking_view(request):
    if request.method == 'POST':
        try:
            room_id = request.POST.get('room')
            title = request.POST.get('title')
            start_time = parse_datetime(request.POST.get('start_time'))
            end_time = parse_datetime(request.POST.get('end_time'))

            conflicting_bookings = Booking.objects.filter(
                room_id=room_id,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(status='REJECTED').exists()

            if conflicting_bookings:
                messages.error(request, 'ช่วงเวลาที่เลือกซ้อนทับกับการจองอื่น')
            else:
                Booking.objects.create(
                    room_id=room_id,
                    title=title,
                    start_time=start_time,
                    end_time=end_time,
                    booked_by=request.user,
                    status='APPROVED' # ตั้งเป็นอนุมัติเลยเพื่อความง่ายในเวอร์ชันนี้
                )
                messages.success(request, 'สร้างการจองสำเร็จแล้ว')
        except Exception as e:
            messages.error(request, f'เกิดข้อผิดพลาด: {e}')
        
        return redirect('calendar')

# --- API สำหรับส่งข้อมูลให้ FullCalendar ---
@login_required
def resources_api(request):
    rooms = Room.objects.all()
    resources = [{'id': str(room.id), 'title': room.name} for room in rooms]
    return JsonResponse(resources, safe=False)

@login_required
def bookings_api(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    bookings = Booking.objects.filter(start_time__gte=start, end_time__lte=end)
    events = []
    for booking in bookings:
        color = '#0d6efd' if booking.status == 'APPROVED' else '#ffc107'
        events.append({
            'id': booking.id,
            'resourceId': str(booking.room.id),
            'title': f"{booking.title}\n({booking.booked_by.username})",
            'start': booking.start_time.isoformat(),
            'end': booking.end_time.isoformat(),
            'color': color,
        })
    return JsonResponse(events, safe=False)