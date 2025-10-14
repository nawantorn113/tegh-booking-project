# booking/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # หน้าหลักและ API
    path('', views.dashboard_view, name='dashboard'),
    path('api/bookings/', views.bookings_api_view, name='api_bookings'),

    # การ Login/Logout
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # การจัดการ Booking
    path('booking/new/', views.create_booking_view, name='create_booking'),
    path('booking/update/<int:booking_id>/', views.update_booking_time_view, name='update_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]