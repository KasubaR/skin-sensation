from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('staff/', views.staff_list, name='staff_list'),
    path('calculate/', views.calculate_totals, name='calculate_totals'),
    path('availability/', views.availability, name='availability'),
    path('appointments/', views.create_appointment, name='create_appointment'),
]
