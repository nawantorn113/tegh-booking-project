from django.urls import path
from . import views

urlpatterns = [
    # หน้าหลักและ Auth
    path('', views.calendar_view, name='calendar'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # หน้าที่สำหรับจัดการการจอง
    path('booking/create/', views.create_booking_view, name='create_booking'),

    # API Endpoints
    path('api/resources/', views.resources_api, name='api_resources'),
    path('api/bookings/', views.bookings_api, name='api_bookings'),
]