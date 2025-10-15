# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('profile/', views.edit_profile_view, name='edit_profile'),
    path('reports/', views.reports_view, name='reports'),

    # Room Management
    path('management/rooms/', views.room_management_view, name='rooms'),
    path('management/rooms/add/', views.add_room_view, name='add_room'),
    path('management/rooms/<int:room_id>/edit/', views.edit_room_view, name='edit_room'),
    path('management/rooms/<int:room_id>/delete/', views.delete_room_view, name='delete_room'),

    # Calendar & Booking
    path('room/<int:room_id>/calendar/', views.room_calendar_view, name='room_calendar'),
    path('api/bookings/', views.bookings_api, name='api_bookings'),
    path('booking/new/<int:room_id>/', views.create_booking_view, name='create_booking_for_room'),
    path('booking/<int:booking_id>/edit/', views.edit_booking_view, name='edit_booking'),
    path('booking/<int:booking_id>/delete/', views.delete_booking_view, name='delete_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]