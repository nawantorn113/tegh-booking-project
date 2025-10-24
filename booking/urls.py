# booking/urls.py
# [ฉบับสมบูรณ์ - ไม่มีรูปภาพ, แก้ไข change_password]

from django.urls import path
from . import views

urlpatterns = [
    # --- Authentication ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'), # หน้าเปลี่ยนรหัสผ่าน

    # --- Main Pages ---
    path('', views.dashboard_view, name='dashboard'),
    path('master-calendar/', views.master_calendar_view, name='master_calendar'),
    path('history/', views.history_view, name='history'),

    # --- Booking related ---
    path('room/<int:room_id>/calendar/', views.room_calendar_view, name='room_calendar'),
    path('booking/<int:room_id>/create/', views.create_booking_view, name='create_booking_for_room'),
    path('booking/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking'), # For cancelling via history page

    # --- APIs ---
    path('api/bookings/', views.bookings_api, name='api_bookings'),
    path('api/rooms/', views.rooms_api, name='api_rooms'),
    path('api/booking/update-time/', views.update_booking_time_api, name='api_update_booking_time'),
    path('api/booking/delete/<int:booking_id>/', views.delete_booking_api, name='delete_booking_api'), # API for cancelling via calendar

    # --- Autocomplete ---
    # (Comment out if dal_select2 is not installed)
    path('user-autocomplete/', views.UserAutocomplete.as_view(), name='user-autocomplete'),

    # --- Approvals ---
    path('approvals/', views.approvals_view, name='approvals'),
    path('approvals/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('approvals/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),

    # --- Management ---
    path('management/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('management/users/', views.user_management_view, name='user_management'),
    path('management/users/<int:user_id>/edit/', views.edit_user_roles_view, name='edit_user_roles'),
    path('management/rooms/', views.room_management_view, name='rooms'),
    path('management/rooms/add/', views.add_room_view, name='add_room'),
    path('management/rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    path('management/rooms/<int:room_id>/delete/', views.delete_room_view, name='delete_room'),

    # --- Reports ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_reports_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),
]