from django.urls import path

from dashboard import contact_views, gallery_views, testimonial_views, views

app_name = 'dashboard'

urlpatterns = [
  path('', views.home, name='home'),
  path('reports/', views.reports, name='reports'),
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
  path('contact-messages/', contact_views.contact_message_list, name='contact_message_list'),
  path(
    'contact-messages/<int:pk>/',
    contact_views.contact_message_detail,
    name='contact_message_detail',
  ),
  path(
    'contact-messages/<int:pk>/delete/',
    contact_views.contact_message_delete,
    name='contact_message_delete',
  ),
  path('business-settings/', contact_views.business_settings_edit, name='business_settings'),
  path('gallery/', gallery_views.gallery_list, name='gallery_list'),
  path('gallery/new/', gallery_views.gallery_create, name='gallery_create'),
  path('gallery/<int:pk>/', gallery_views.gallery_edit, name='gallery_edit'),
  path('gallery/<int:pk>/delete/', gallery_views.gallery_delete, name='gallery_delete'),
  path('reviews/', testimonial_views.testimonial_list, name='testimonial_list'),
  path('reviews/<int:pk>/', testimonial_views.testimonial_detail, name='testimonial_detail'),
  path(
    'reviews/<int:pk>/approve/',
    testimonial_views.testimonial_approve,
    name='testimonial_approve',
  ),
  path(
    'reviews/<int:pk>/reject/',
    testimonial_views.testimonial_reject,
    name='testimonial_reject',
  ),
  path(
    'reviews/<int:pk>/feature/',
    testimonial_views.testimonial_feature,
    name='testimonial_feature',
  ),
  path(
    'reviews/<int:pk>/delete/',
    testimonial_views.testimonial_delete,
    name='testimonial_delete',
  ),
]
