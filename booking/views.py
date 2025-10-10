from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Booking, Room
from datetime import datetime, timedelta
import json
import requests
from django.core.mail import send_mail
from django.conf import settings

LINE_TOKEN = 'YOUR_LINE_NOTIFY_TOKEN'

def send_line_notify(message):
    headers = {"Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"message": message}
    requests.post("https://notify-api.line.me/api/notify", headers=headers, data=payload)

def send_booking_email(booking):
    subject = f"[TEGH] การจองห้อง {booking.room.name} - {booking.status}"
    message = f"รายละเอียด: {booking.title}\nเริ่ม: {booking.start_time}\nสิ้นสุด: {booking.end_time}"
    recipients = [booking.user.email]
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)

@login_required
def dashboard(request):
    rooms = Room.objects.all()
    return render(request, 'dashboard.html', {'rooms': rooms})

@login_required
def bookings_json(request):
    bookings = Booking.objects.all()
    events = []
    for b in bookings:
        color = '#28a745' if b.status=='APPROVED' else '#ffc107' if b.status=='PENDING' else '#dc3545'
        events.append({
            'id': b.id,
            'title': b.title,
            'start': b.start_time.isoformat(),
            'end': b.end_time.isoformat(),
            'color': color
        })
    return JsonResponse(events, safe=False)

@login_required
def create_booking(request):
    if request.method == 'POST':
        data = request.POST
        room = Room.objects.get(id=data['room'])
        start_time = datetime.fromisoformat(data['start_time'])
        end_time = datetime.fromisoformat(data['end_time'])
        booking = Booking.objects.create(
            room=room,
            user=request.user,
            title=data['title'],
            start_time=start_time,
            end_time=end_time,
            recurring=data.get('recurring','NONE')
        )
        send_booking_email(booking)
        send_line_notify(f"จองห้อง {booking.room.name} โดย {booking.user.username} สถานะ: {booking.status}")

        # Recurring
        if booking.recurring != 'NONE':
            occurrences = 5
            for i in range(1, occurrences):
                delta = timedelta(days=i) if booking.recurring=='DAILY' else \
                        timedelta(weeks=i) if booking.recurring=='WEEKLY' else \
                        timedelta(days=30*i)
                Booking.objects.create(
                    room=room,
                    user=request.user,
                    title=booking.title,
                    start_time=start_time+delta,
                    end_time=end_time+delta
                )
        return redirect('dashboard')

@login_required
def update_booking_time(request, booking_id):
    booking = Booking.objects.get(id=booking_id)
    if request.method=='POST':
        data = json.loads(request.body)
        booking.start_time = datetime.fromisoformat(data['start'])
        booking.end_time = datetime.fromisoformat(data['end'])
        booking.save()
        return JsonResponse({'status':'success'})
