from django.urls import include, path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('services/', views.services, name='services'),
    path('services/<slug:service_slug>/', views.service_treatments, name='service_treatments'),
    path(
        'services/<slug:service_slug>/<slug:treatment_slug>/',
        views.treatment_detail,
        name='treatment_detail',
    ),
    path('booking/', views.booking, name='booking'),
    path('gallery/', views.gallery, name='gallery'),
    path('', include('communications.urls')),
    path('', include('testimonials.urls')),
]
