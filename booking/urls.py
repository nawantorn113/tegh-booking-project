from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Pages (จาก Sidebar)
    path('', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('rooms/', views.room_management_view, name='rooms'),

    # Actions
    path('booking/new/', views.create_booking_view, name='create_booking'),
    path('booking/<int:booking_id>/approve/', views.approve_booking_view, name='approve_booking'),
    path('booking/<int:booking_id>/reject/', views.reject_booking_view, name='reject_booking'),
]