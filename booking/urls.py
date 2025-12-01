from django.urls import path
from . import views

urlpatterns = [
    # --- Main Pages ---
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('calendar/master/', views.master_calendar_view, name='master_calendar'),
    path('calendar/public/', views.public_calendar_view, name='public_calendar'), # หน้าปฏิทินรวมแบบ Public
    
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    
    # --- Authentication ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('sso-login/', views.sso_login_view, name='sso_login'),
    
    # --- Autocomplete ---
    path('user-autocomplete/', views.UserAutocomplete.as_view(), name='user-autocomplete'),

    # --- Room & Booking Actions ---
    path('room/<int:room_id>/', views.room_calendar_view, name='room_calendar'),
    path('booking/create/<int:room_id>/', views.create_booking_view, name='create_booking'),
    path('booking/detail/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('booking/edit/<int:booking_id>/', views.edit_booking_view, name='edit_booking'),
    path('booking/delete/<int:booking_id>/', views.delete_booking_view, name='delete_booking'),
    path('booking/approve/<int:booking_id>/', views.approve_booking_view, name='approve_booking'),
    path('booking/reject/<int:booking_id>/', views.reject_booking_view, name='reject_booking'),
    
    # --- Management ---
    path('manage/rooms/', views.room_management_view, name='rooms'),
    path('manage/rooms/add/', views.add_room_view, name='add_room'),
    path('manage/rooms/edit/<int:room_id>/', views.edit_room_view, name='edit_room'),
    path('manage/rooms/delete/<int:room_id>/', views.delete_room_view, name='delete_room'),
    path('manage/users/', views.user_management_view, name='user_management'),
    path('manage/users/add/', views.add_user_view, name='add_user'),
    path('manage/users/edit/<int:user_id>/', views.edit_user_roles_view, name='edit_user_roles'),
    path('manage/logs/', views.audit_log_view, name='audit_log'),
    
    # --- Reports & Export ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_pdf'),
    
    # --- Search & APIs ---
    path('search/', views.smart_search_view, name='smart_search'),
    path('api/rooms/', views.rooms_api, name='rooms_api'),
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/booking/update/', views.update_booking_time_api, name='update_booking_time_api'),
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'),
    
    # --- Webhooks ---
    path('webhooks/line/', views.line_webhook, name='line_webhook'),
]