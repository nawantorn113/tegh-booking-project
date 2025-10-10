from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('booking/new/', views.create_booking_view, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]