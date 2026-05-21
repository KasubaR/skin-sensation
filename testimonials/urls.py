from django.urls import path

from testimonials import views

urlpatterns = [
    path('testimonials/', views.testimonial_list, name='testimonials'),
    path('reviews/create/', views.review_create, name='review_create'),
]
