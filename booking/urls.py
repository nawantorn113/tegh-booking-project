from django.urls import path
from . import views
# สำหรับ Autocomplete (ถ้าใช้ dal)
from .views import UserAutocomplete, EquipmentAutocomplete

urlpatterns = [
    # --- 1. หน้าแรก (Root) ---
    # [แก้ไข] เข้าเว็บปุ๊บ เจอหน้าปฏิทินรวมทันที (ไม่ต้อง Login)
    path('', views.public_calendar_view, name='root'),
    
    # หรือถ้าต้องการเข้าผ่าน url /public-calendar/ ก็ยังเข้าได้
    path('public-calendar/', views.public_calendar_view, name='public_calendar'),

    # --- 2. Auth & Dashboard ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Outlook Auth (ถ้ามี)
    path('outlook/login/', views.outlook_login_view, name='outlook_login'),
    path('outlook/callback/', views.outlook_callback_view, name='outlook_callback'),

    # --- 3. การค้นหา (Smart Search) ---
    path('search/', views.smart_search_view, name='smart_search'),

    # --- 4. ปฏิทินและการจอง ---
    path('master-calendar/', views.master_calendar_view, name='master_calendar'),
    path('room/<int:room_id>/calendar/', views.room_calendar_view, name='room_calendar'),
    
    # รายละเอียด / แก้ไข / ยกเลิก
    path('booking/<int:booking_id>/detail/', views.booking_detail_view, name='booking_detail'),
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking'),
    path('history/', views.history_view, name='history'),

    # --- 5. การอนุมัติ (Admin/Approver) ---
    path('approvals/', views.approvals_view, name='approvals'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),

    # --- 6. จัดการห้องประชุม (Admin) ---
    path('manage/rooms/', views.room_management_view, name='rooms'),
    path('manage/rooms/add/', views.add_room_view, name='add_room'),
    path('manage/rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    path('manage/rooms/<int:room_id>/delete/', views.delete_room_view, name='delete_room'),
    
    # [สำคัญ] ปุ่มเปิดใช้งานห้อง (สำหรับเลิกปิดปรับปรุง)
    path('manage/rooms/<int:room_id>/open/', views.open_room_view, name='open_room'),

    # --- 7. จัดการอุปกรณ์ (Admin) ---
    path('manage/equipments/', views.equipment_management_view, name='equipments'),
    path('manage/equipments/add/', views.add_equipment_view, name='add_equipment'),
    path('manage/equipments/<int:eq_id>/edit/', views.edit_equipment_view, name='edit_equipment'),
    path('manage/equipments/<int:eq_id>/delete/', views.delete_equipment_view, name='delete_equipment'),

    # --- 8. จัดการผู้ใช้งาน (Admin) ---
    path('manage/users/', views.user_management_view, name='user_management'),
    path('manage/users/add/', views.add_user_view, name='add_user'),
    path('manage/users/<int:user_id>/edit/', views.edit_user_view, name='edit_user'),
    path('manage/users/<int:user_id>/roles/', views.edit_user_roles_view, name='edit_user_roles'),

    # --- 9. รายงานและ Logs ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_reports_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),
    path('audit-log/', views.audit_log_view, name='audit_log'),

    # --- 10. API Endpoints (สำหรับ JavaScript/AJAX) ---
    path('api/bookings/', views.bookings_api, name='bookings_api'), # ดึงข้อมูลลงปฏิทิน
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'), # แจ้งเตือนกระดิ่ง
    path('api/booking/update-time/', views.update_booking_time_api, name='update_booking_time_api'), # ลากวาง
    path('api/booking/delete/', views.delete_booking_api, name='delete_booking_api'),
    path('api/notification/read/<int:booking_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # [API แจ้งปัญหา] ที่เราเพิ่งคุยกัน (ถ้าคุณเพิ่มใน views.py แล้ว)
    # path('api/report-issue/', views.report_issue_api, name='report_issue_api'),

    # --- 11. Autocomplete URLs ---
    path('user-autocomplete/', UserAutocomplete.as_view(), name='user-autocomplete'),
    path('equipment-autocomplete/', EquipmentAutocomplete.as_view(), name='equipment-autocomplete'),
]