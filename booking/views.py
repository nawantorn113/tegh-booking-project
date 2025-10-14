# booking/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.conf import settings
from .models import Booking, Room
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

# --- Views หลักของระบบ ---
@login_required
def dashboard_view(request): # [แก้ไข] เปลี่ยนชื่อฟังก์ชันเป็น dashboard_view
    rooms = Room.objects.all()
    return render(request, 'dashboard.html', {'rooms': rooms})

@login_required
def bookings_api_view(request): # [แก้ไข] เปลี่ยนชื่อฟังก์ชันให้สื่อความหมายมากขึ้น
    bookings = Booking.objects.all()
    events = []
    for b in bookings:
        color = '#198754' if b.status=='APPROVED' else '#ffc107' if b.status=='PENDING' else '#dc3545'
        events.append({
            'id': b.id,
            'title': f"{b.title}\n({b.booked_by.username})",
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(),
            'resourceId': b.room.id, # สำคัญสำหรับ FullCalendar Resource View
            'color': color,
        })
    return JsonResponse(events, safe=False)

@login_required
def create_booking_view(request): # [แก้ไข] เปลี่ยนชื่อฟังก์ชันเป็น create_booking_view
    if request.method == 'POST':
        data = request.POST
        try:
            room = get_object_or_404(Room, id=data['room'])
            start_time = parse_datetime(data['start_time'])
            end_time = parse_datetime(data['end_time'])
            recurring_type = data.get('recurring', 'NONE')

            # สร้างการจองหลัก
            booking = Booking.objects.create(
                room=room,
                booked_by=request.user, # [แก้ไข] ใช้ "booked_by" แทน "user"
                title=data['title'],
                start_time=start_time,
                end_time=end_time,
                recurring=recurring_type
            )
            messages.success(request, f"การจองห้อง '{room.name}' สำเร็จแล้ว")
            send_line_notify(f"จองห้อง: {booking.room.name}\nหัวข้อ: {booking.title}\nโดย: {booking.booked_by.username}\nสถานะ: {booking.get_status_display()}")

            # สร้างการจองซ้ำ (ถ้ามี)
            if recurring_type != 'NONE':
                occurrences = 4 # สร้างล่วงหน้า 4 ครั้ง
                for i in range(1, occurrences + 1):
                    if recurring_type == 'DAILY': delta = timedelta(days=i)
                    elif recurring_type == 'WEEKLY': delta = timedelta(weeks=i)
                    else: delta = timedelta(days=30*i) # การประมาณค่ารายเดือน

                    Booking.objects.create(
                        room=room,
                        booked_by=request.user, # [แก้ไข] ใช้ "booked_by"
                        title=booking.title,
                        start_time=start_time + delta,
                        end_time=end_time + delta,
                        recurring='NONE' # การจองย่อยไม่ต้องมี recurring อีก
                    )
            
            return redirect('dashboard')
        
        except Exception as e:
            messages.error(request, f"เกิดข้อผิดพลาดในการจอง: {e}")
            return redirect('dashboard')

    return redirect('dashboard') # ถ้าไม่ใช่ POST ให้กลับไปหน้าหลัก

@login_required
def update_booking_time_view(request, booking_id): # [แก้ไข] เปลี่ยนชื่อฟังก์ชัน
    booking = get_object_or_404(Booking, id=booking_id, booked_by=request.user) # เพิ่มเงื่อนไขให้แก้ได้เฉพาะของตัวเอง
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