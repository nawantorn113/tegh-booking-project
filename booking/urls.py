from django.urls import path
from . import views
# 💡 [CRITICAL] ต้อง Import Class-based View 
from .views import UserAutocomplete, rooms_api, bookings_api, update_booking_time_api, delete_booking_api 

urlpatterns = [
    # --- Auth Views ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('sso-login/', views.sso_login_view, name='sso_login'), 
    path('public/calendar/', views.public_calendar_view, name='public_calendar'), 
    path('manage/users/add/', views.add_user_view, name='add_user'),
    
    # --- Core Views ---
    path('', views.master_calendar_view, name='master_calendar'), 
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('search/', views.smart_search_view, name='smart_search'),
    
    # --- Room & Booking Views ---
    path('room/calendar/<int:room_id>/', views.room_calendar_view, name='room_calendar'),
    path('booking/create/<int:room_id>/', views.create_booking_view, name='create_booking'),
    path('booking/detail/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('booking/edit/<int:booking_id>/', views.edit_booking_view, name='edit_booking'),
    path('booking/delete/<int:booking_id>/', views.delete_booking_view, name='delete_booking'),
    
    # --- Approvals Views (แก้ AttributeError) ---
    path('approvals/', views.approvals_view, name='approvals'),
    path('approvals/approve/<int:booking_id>/', views.approve_booking_view, name='approve_booking'),
    path('approvals/reject/<int:booking_id>/', views.reject_booking_view, name='reject_booking'),

    # --- Management Views ---
    path('manage/rooms/', views.room_management_view, name='rooms'),
    path('manage/rooms/add/', views.add_room_view, name='add_room'),
    path('manage/rooms/edit/<int:room_id>/', views.edit_room_view, name='edit_room'),
    path('manage/rooms/delete/<int:room_id>/', views.delete_room_view, name='delete_room'),
    
    path('manage/users/', views.user_management_view, name='user_management'),
    path('manage/users/edit/<int:user_id>/', views.edit_user_roles_view, name='edit_user_roles'),
    
    path('manage/audit-log/', views.audit_log_view, name='audit_log'),
    
    # --- Reports & Exports ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_pdf'), 
    
    # --- APIs / Autocomplete ---
    path('api/user-autocomplete/', UserAutocomplete.as_view(), name='user-autocomplete'), 
    path('api/rooms/', views.rooms_api, name='rooms_api'),
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/booking/update/time/', views.update_booking_time_api, name='update_booking_time_api'),
    path('api/booking/delete/<int:booking_id>/', views.delete_booking_api, name='delete_booking_api'),
    
    # --- Outlook Integration ---
    path('outlook/connect/', views.outlook_connect, name='outlook_connect'),
    path('outlook/callback/', views.outlook_callback, name='outlook_callback'),
    
    # --- Teams Receiver ---
    path('teams/action/', views.teams_action_receiver, name='teams_action_receiver'),
]