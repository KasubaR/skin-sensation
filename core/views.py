from django.shortcuts import render


def home(request):
    return render(
        request,
        'index.html',
        {
            # Set True when the shop / featured products section is ready.
            'show_featured_products': False,
        },
    )


def services(request):
    return render(request, 'services.html')


def booking(request):
    return render(request, 'booking.html')


def gallery(request):
    return render(request, 'gallery.html')
