# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- 💡💡💡 [นี่คือจุดที่แก้ไข] 💡💡💡 ---
    # (เพิ่ม 2 บรรทัดนี้สำหรับ Login / Logout)
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # --- Main Pages ---
    path('', views.dashboard_view, name='dashboard'),
    path('room/<int:room_id>/', views.room_calendar_view, name='room_calendar'),
    path('history/', views.history_view, name='history'),
    path('booking/detail/<int:booking_id>/', views.booking_detail_view, name='booking_detail'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('search/', views.smart_search_view, name='smart_search'),
    path('master-calendar/', views.master_calendar_view, name='master_calendar'),

    # --- Booking Actions ---
    path('booking/create/<int:room_id>/', views.create_booking_view, name='create_booking'),
    path('edit/<int:booking_id>/', views.edit_booking_view, name='edit_booking'),
    path('delete/<int:booking_id>/', views.delete_booking_view, name='delete_booking'),

    # --- APIs ---
    path('api/rooms/', views.rooms_api, name='rooms_api'),
    path('api/bookings/', views.bookings_api, name='bookings_api'),
    path('api/update-time/', views.update_booking_time_api, name='update_booking_time'),
    path('api/delete-booking/<int:booking_id>/', views.delete_booking_api, name='delete_booking_api'),

    # --- (URL สำหรับ Autocomplete) ---
    path('user-autocomplete/', views.UserAutocomplete.as_view(), name='user-autocomplete'),

    # --- Admin / Approvals ---
    path('approvals/', views.approvals_view, name='approvals'),
    path('approve/<int:booking_id>/', views.approve_booking_view, name='approve_booking'),
    path('reject/<int:booking_id>/', views.reject_booking_view, name='reject_booking'),
    
    # --- Admin / Management ---
    path('manage/users/', views.user_management_view, name='user_management'),
    path('manage/users/<int:user_id>/', views.edit_user_roles_view, name='edit_user_roles'),
    path('manage/rooms/', views.room_management_view, name='rooms'),
    path('manage/rooms/add/', views.add_room_view, name='add_room'),
    path('manage/rooms/edit/<int:room_id>/', views.edit_room_view, name='edit_room'),
    path('manage/rooms/delete/<int:room_id>/', views.delete_room_view, name='delete_room'),
    
    # --- Admin / Reports ---
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/excel/', views.export_reports_excel, name='export_excel'),
    path('reports/export/pdf/', views.export_reports_pdf, name='export_pdf'),
]