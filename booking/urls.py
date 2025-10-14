# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Pages (จาก Sidebar)
    path('', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('rooms/', views.room_management_view, name='rooms'),
    path('profile/', views.edit_profile_view, name='edit_profile'),

    # Actions (ส่วนของการกระทำต่างๆ)
    # [แก้ไข] เพิ่มบรรทัดนี้กลับเข้ามาให้ถูกต้อง
    path('booking/new/', views.create_booking_view, name='create_booking'),

    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]