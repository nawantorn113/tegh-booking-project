from django.urls import path
from . import views

urlpatterns = [

    path('', views.dashboard_view, name='home'), 

    # --- Dashboard & Calendar ---
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('calendar/master/', views.master_calendar_view, name='master_calendar'),
    path('calendar/public/', views.public_calendar_view, name='public_calendar'),
    path('calendar/room/<int:room_id>/', views.room_calendar_view, name='room_calendar'),
    
    # --- Booking CRUD ---
    path('booking/create/<int:room_id>/', views.room_calendar_view, name='create_booking'),
    
    # (สลับตำแหน่ง ID ให้ตรงกับที่หน้าเว็บส่งมา)
    path('booking/<int:booking_id>/detail/', views.booking_detail_view, name='booking_detail'),
    
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking'),
    
    # --- History & Approvals ---
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
    
    # --- Search & Tools ---
    path('search/', views.smart_search_view, name='smart_search'),
    path('user-autocomplete/', views.UserAutocomplete.as_view(), name='user-autocomplete'),
    
    # --- Auth & Outlook ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('outlook/login/', views.outlook_login_view, name='outlook_login'),
    path('outlook/callback/', views.outlook_callback_view, name='outlook_callback'),
    
    # --- Admin Management ---
    path('manage/rooms/', views.room_management_view, name='rooms'),
    path('manage/rooms/add/', views.add_room_view, name='add_room'),
    path('manage/rooms/edit/<int:room_id>/', views.edit_room_view, name='edit_room'),
    path('manage/rooms/delete/<int:room_id>/', views.delete_room_view, name='delete_room'),
    
    path('manage/users/', views.user_management_view, name='user_management'),
    path('manage/users/add/', views.add_user_view, name='add_user'),
    path('manage/users/edit-roles/<int:user_id>/', views.edit_user_roles_view, name='edit_user_roles'),
    
    # Equipment Management
    path('manage/equipments/', views.equipment_management_view, name='equipments'),
    path('manage/equipments/add/', views.add_equipment_view, name='add_equipment'),
    path('equipment-autocomplete/', views.EquipmentAutocomplete.as_view(), name='equipment-autocomplete'),
    path('manage/equipments/delete/<int:eq_id>/', views.delete_equipment_view, name='delete_equipment'),

    # --- Audit Log & Reports ---
    path('audit-log/', views.audit_log_view, name='audit_log'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_pdf'),
    
    # --- API ---
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/booking/update-time/', views.update_booking_time_api, name='update_booking_time_api'),
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'),
    path('api/delete-booking/<int:booking_id>/', views.delete_booking_api, name='delete_booking_api'),
    path('teams/webhook/', views.teams_action_receiver, name='teams_webhook'),

# แจ้งเตือนรับทราบการอนุมัติ
    path('api/mark-read/<int:booking_id>/', views.mark_notification_read, name='mark_notification_read'),
]