# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- Auth, Pages ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('rooms/', views.room_management_view, name='rooms'),
    path('profile/', views.edit_profile_view, name='edit_profile'),

    # --- หน้าปฏิทินของแต่ละห้อง (ที่เคย Error) ---
    path('room/<int:room_id>/calendar/', views.room_calendar_view, name='room_calendar'),

    # --- APIs ---
    path('api/bookings/', views.bookings_api, name='api_bookings'),

    # --- Actions ---
    path('booking/new/<int:room_id>/', views.create_booking_view, name='create_booking_for_room'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]