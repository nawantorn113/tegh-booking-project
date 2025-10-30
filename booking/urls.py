from django.urls import path
from . import views

urlpatterns = [
    # --- Authentication ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password/', views.change_password_view, name='change_password'),

    # --- Main Pages ---
    path('', views.dashboard_view, name='dashboard'),
    path('search/', views.smart_search_view, name='smart_search'),
    path('calendar/', views.master_calendar_view, name='master_calendar'),
    path('history/', views.history_view, name='history'),

    # --- Booking & Rooms ---
    path('room/<int:room_id>/', views.room_calendar_view, name='room_calendar'),
    path('room/<int:room_id>/book/', views.create_booking_view, name='create_booking'),
    path('booking/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking_view'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking_view'),

    # --- Approvals (Admin/Approver) ---
    path('approvals/', views.approvals_view, name='approvals'),
    path('approvals/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('approvals/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),

    # --- Management (Admin) ---
    path('management/users/', views.user_management_view, name='user_management'),
    path('management/users/<int:user_id>/edit/', views.edit_user_roles_view, name='edit_user_roles'),
    path('management/rooms/', views.room_management_view, name='rooms'), 
    path('management/rooms/add/', views.add_room_view, name='add_room'),
    path('management/rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    path('management/rooms/<int:room_id>/delete/', views.delete_room_view, name='delete_room'),

    # --- Reports (Admin) ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_reports_excel'),
    # (ถ้าคุณอยากเปิด PDF ให้ลบ # ออก และไปแก้ใน views.py)
    # path('reports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),

    # --- APIs (for FullCalendar / Select2) ---
    path('api/rooms/', views.rooms_api, name='rooms_api'),
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/bookings/update/', views.update_booking_time_api, name='update_booking_time_api'),
    path('api/bookings/<int:booking_id>/delete/', views.delete_booking_api, name='delete_booking_api'),

    # --- ⬇️ (แก้ไข!) ย้าย Path มาไว้ข้างในลิสต์นี้ ⬇️ ---
    path('api/user-autocomplete/', views.UserAutocomplete.as_view(), name='user_autocomplete')
]

# --- ⬆️ (ลบ .append() ที่อยู่ท้ายไฟล์ทิ้ง) ⬆️ ---