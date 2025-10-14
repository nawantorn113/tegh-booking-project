# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # หน้าหลัก
    path('', views.dashboard_view, name='dashboard'),
    
    # [สำคัญ] เพิ่มบรรทัดนี้กลับเข้าไปให้ถูกต้อง
    path('login/', views.login_view, name='login'),
    
    # URL อื่นๆ ที่จำเป็น
    path('logout/', views.logout_view, name='logout'),
    path('booking/new/', views.create_booking_view, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]