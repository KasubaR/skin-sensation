from django.urls import include, path

from accounts import views

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal_dashboard'),
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
    path('payments/', views.payment_list, name='payment_list'),
    path(
        'payments/upload/<str:booking_reference>/',
        views.payment_upload,
        name='payment_upload',
    ),
    path('payments/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path(
        'payments/<int:payment_id>/receipt.pdf',
        views.payment_receipt_pdf,
        name='payment_receipt_pdf',
    ),
    path('profile/', views.profile_detail, name='profile_detail'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/password/', views.profile_password, name='profile_password'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/create/', views.review_create_redirect, name='review_create_portal'),
    path('resend-confirmation/', views.resend_confirmation_email, name='resend_confirmation'),
    path('', include('allauth.urls')),
]
