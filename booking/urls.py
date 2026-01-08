from django.urls import path
from . import views

urlpatterns = [
    # [จุดที่ 1] หน้าแรก (Root URL) -> ให้แสดงปฏิทินรวมทันที
    path('', views.public_calendar_view, name='root'),
    
    # URL เดิมอื่นๆ
    path('public_calendar/', views.public_calendar_view, name='public_calendar'), # เผื่อใครเข้าลิงก์เก่า
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('outlook/login/', views.outlook_login_view, name='outlook_login'),
    path('outlook/callback/', views.outlook_callback_view, name='outlook_callback'),
    
    # Calendar & Booking
    path('master-calendar/', views.master_calendar_view, name='master_calendar'),
    path('room/<int:room_id>/calendar/', views.room_calendar_view, name='room_calendar'),
    path('booking/<int:booking_id>/detail/', views.booking_detail_view, name='booking_detail'),
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking'),
    path('history/', views.history_view, name='history'),
    
    # Approvals
    path('approvals/', views.approvals_view, name='approvals'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
    
    # Admin Management
    path('rooms/', views.room_management_view, name='rooms'),
    path('rooms/add/', views.add_room_view, name='add_room'),
    path('rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    path('rooms/<int:room_id>/delete/', views.delete_room_view, name='delete_room'),
    
    path('users/', views.user_management_view, name='user_management'),
    path('users/add/', views.add_user_view, name='add_user'),
    path('users/<int:user_id>/edit/', views.edit_user_view, name='edit_user'),
    path('users/<int:user_id>/roles/', views.edit_user_roles_view, name='edit_user_roles'),
    
    path('equipments/', views.equipment_management_view, name='equipments'),
    path('equipments/add/', views.add_equipment_view, name='add_equipment'),
    path('equipments/<int:eq_id>/edit/', views.edit_equipment_view, name='edit_equipment'),
    path('equipments/<int:eq_id>/delete/', views.delete_equipment_view, name='delete_equipment'),
    
    path('audit-log/', views.audit_log_view, name='audit_log'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_reports_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),
    
    path('search/', views.smart_search_view, name='smart_search'),
    
    # APIs
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/booking/update-time/', views.update_booking_time_api, name='update_booking_time_api'),
    path('api/booking/<int:booking_id>/delete/', views.delete_booking_api, name='delete_booking_api'),
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'),
    path('api/notification/read/<int:booking_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # Autocomplete
    path('user-autocomplete/', views.UserAutocomplete.as_view(), name='user-autocomplete'),
    path('equipment-autocomplete/', views.EquipmentAutocomplete.as_view(), name='equipment-autocomplete'),
    
    path('teams/action/', views.teams_action_receiver, name='teams_action'),
]