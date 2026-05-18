from django.urls import path

from dashboard import views

app_name = 'dashboard'

urlpatterns = [
  path('', views.home, name='home'),
  path('appointments/calendar/', views.appointment_calendar, name='appointment_calendar'),
  path('api/appointments/', views.appointment_calendar_api, name='appointment_calendar_api'),
  path('appointments/schedule/', views.appointment_schedule, name='appointment_schedule'),
  path('appointments/', views.appointment_list, name='appointment_list'),
  path(
    'appointments/<str:booking_reference>/',
    views.appointment_detail,
    name='appointment_detail',
  ),
  path('payments/', views.payment_list, name='payment_list'),
  path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
  path('services/', views.service_list, name='service_list'),
  path('services/new/', views.service_create, name='service_create'),
  path('services/<int:pk>/', views.service_edit, name='service_edit'),
  path('treatments/new/', views.treatment_create, name='treatment_create'),
  path('treatments/<int:pk>/', views.treatment_edit, name='treatment_edit'),
  path('customers/', views.customer_list, name='customer_list'),
  path('customers/<int:user_id>/', views.customer_detail, name='customer_detail'),
]
