from django.urls import include, path

from accounts import views

urlpatterns = [
    path('appointments/', views.appointment_list, name='appointment_list'),
    path(
        'appointments/<str:booking_reference>/',
        views.appointment_detail,
        name='appointment_detail',
    ),
    path(
        'appointments/<str:booking_reference>/cancel/',
        views.appointment_cancel,
        name='appointment_cancel',
    ),
    path(
        'appointments/<str:booking_reference>/reschedule/',
        views.appointment_reschedule,
        name='appointment_reschedule',
    ),
    path(
        'appointments/<str:booking_reference>/receipt/',
        views.appointment_receipt,
        name='appointment_receipt',
    ),
    path('', include('allauth.urls')),
]
