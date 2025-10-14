# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # หน้าหลัก
    path('', views.dashboard_view, name='dashboard'),
    
    # API สำหรับดึงข้อมูลไปแสดงในปฏิทิน
    path('api/bookings/', views.bookings_api_view, name='api_bookings'),
    
    # URL สำหรับสร้างและแก้ไขการจอง
    path('booking/create/', views.create_booking_view, name='create_booking'),
    path('booking/update/<int:booking_id>/', views.update_booking_time_view, name='update_booking'),
]