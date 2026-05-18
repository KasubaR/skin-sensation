from datetime import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import Staff
from bookings.models import DayOfWeek, StaffAvailability
from services.models import Service, Treatment

User = get_user_model()

SERVICES = [
    (
        'nail-treatment',
        'Nail Treatment',
        'Manicures, pedicures, gel, acrylic, and nail art.',
        'Nails & hands',
        1,
    ),
    (
        'massage-therapy',
        'Massage Therapy',
        'Swedish, deep tissue, hot stone, and specialty massage.',
        'Relaxation & recovery',
        2,
    ),
    (
        'facial-treatment',
        'Facial Treatment',
        'Facials, peels, microneedling, and brow services.',
        'Glow & skin health',
        3,
    ),
    (
        'waxing-treatments',
        'Waxing Treatments',
        'Face and body waxing for smooth, lasting results.',
        'Smooth & refined',
        4,
    ),
    (
        'laser-treatments',
        'Laser Treatments',
        'Laser hair removal for face and body.',
        'Long-lasting smoothness',
        5,
    ),
]

# (slug, name, price, duration_minutes, subsection, price_from, price_label)
NAIL_TREATMENTS = [
    ('gel-paint', 'Gel paint', '300.00', 60, '', False, ''),
    ('gel-builder-biab', 'Gel builder (BIAB)', '400.00', 60, '', False, ''),
    ('stick-ons', "Stick-on's", '400.00', 60, '', False, ''),
    ('acrylic', 'Acrylic', '500.00', 75, '', False, ''),
    ('gel-bottle-spa-manicure', 'Gel bottle spa manicure', '500.00', 60, '', False, ''),
    ('manicure-biab', 'Manicure + BIAB', '550.00', 75, '', False, ''),
    ('manicure-stick-ons', "Manicure + Stick on's", '550.00', 75, '', False, ''),
    ('manicure-acrylic', 'Manicure + Acrylic', '600.00', 90, '', False, ''),
    ('regular-pedicure', 'Regular Pedicure', '500.00', 60, '', False, ''),
    ('pedicure-biab', 'Pedicure + BIAB', '650.00', 75, '', False, ''),
    ('pedicure-stick-ons', "Pedicure + Stick on's", '650.00', 75, '', False, ''),
    ('pedicure-acrylic', 'Pedicure + Acrylic', '650.00', 90, '', False, ''),
    ('paraffin-pedicure', 'Paraffin Pedicure', '500.00', 60, '', False, ''),
    ('jelly-pedicure', 'Jelly Pedicure', '550.00', 60, '', False, ''),
    ('refill', 'Refill', '300.00', 45, '', False, ''),
    ('normal-soak-off', 'Normal Soak Off', '50.00', 20, '', False, ''),
    ('soak-off-with-extension', 'Soak Off with Extension', '100.00', 30, '', False, ''),
]

MASSAGE_TREATMENTS = [
    ('swedish-massage', 'Swedish massage', '500.00', 60, '', False, ''),
    ('deep-tissue-massage', 'Deep tissue massage', '600.00', 60, '', False, ''),
    ('aromatherapy-massage', 'Aromatherapy massage', '600.00', 60, '', False, ''),
    ('hot-stone-massage', 'Hot stone massage', '700.00', 75, '', False, ''),
    ('ukuchina-massage', 'Ukuchina massage', '700.00', 75, '', False, ''),
    ('pregnancy-massage', 'Pregnancy massage', '800.00', 60, '', False, ''),
    ('thermal-bliss-massage', 'Thermal bliss massage', '800.00', 75, '', False, ''),
    ('couples-massage', 'Couples massage', '1000.00', 90, '', False, ''),
    ('wood-therapy', 'Wood therapy', '500.00', 60, 'Add-On Treatments', True, 'K500–K1,000'),
    ('body-scrub', 'Body scrub', '500.00', 45, 'Add-On Treatments', False, ''),
    ('body-wrap', 'Body wrap', '500.00', 45, 'Add-On Treatments', False, ''),
]

FACIAL_TREATMENTS = [
    ('classic-facial', 'Classic facial', '500.00', 60, '', False, ''),
    ('microdermabrasion', 'Microdermabrasion', '600.00', 60, '', False, ''),
    ('dermaplane-facial', 'Dermaplane facial', '600.00', 60, '', False, ''),
    ('deep-clean-facial', 'Deep clean facial', '800.00', 75, '', False, ''),
    ('hydra-facial', 'Hydra facial', '800.00', 75, '', False, ''),
    ('vitamin-c-facial', 'Vitamin C facial', '700.00', 60, '', False, ''),
    ('acne-facial', 'Acne facial', '700.00', 60, '', False, ''),
    ('anti-aging-facial', 'Anti-aging facial', '700.00', 75, '', False, ''),
    ('microneedling-facial', 'Microneedling facial', '1000.00', 90, '', False, ''),
    ('microneedling-epsoms', 'Microneedling with Epsoms', '1500.00', 90, '', False, ''),
    ('pigmentation-peel', 'Pigmentation peel', '1000.00', 60, '', False, ''),
    ('acne-peel', 'Acne peel', '1200.00', 60, '', False, ''),
    ('glow-peel', 'Glow peel', '850.00', 60, '', False, ''),
    ('zena-algae-peel', 'Zena algae peel', '1000.00', 60, '', True, ''),
    ('vajacial', 'Vajacial', '500.00', 45, '', False, ''),
    ('eyebrow-tint', 'Eyebrow tint', '200.00', 20, '', False, ''),
    ('eyebrow-lamination', 'Eyebrow lamination', '500.00', 45, '', False, ''),
]

WAXING_TREATMENTS = [
    ('eyebrow-wax', 'Eyebrow wax', '150.00', 15, '', False, ''),
    ('lip-wax', 'Lip wax', '100.00', 10, '', False, ''),
    ('chin-wax', 'Chin wax', '200.00', 15, '', False, ''),
    ('underarm-wax', 'Underarm wax', '300.00', 20, '', False, ''),
    ('half-arm-wax', 'Half arm wax', '300.00', 25, '', False, ''),
    ('full-arm-wax', 'Full arm wax', '500.00', 40, '', False, ''),
    ('chest-wax', 'Chest wax', '400.00', 30, '', False, ''),
    ('abdomen-wax', 'Abdomen wax', '200.00', 20, '', False, ''),
    ('stomach-wax', 'Stomach wax', '400.00', 25, '', False, ''),
    ('bikini-wax', 'Bikini wax', '350.00', 30, '', False, ''),
    ('brazilian-wax', 'Brazilian wax', '400.00', 35, '', False, ''),
    ('hollywood-wax', 'Hollywood wax', '500.00', 45, '', False, ''),
    ('half-leg-wax', 'Half leg wax', '500.00', 35, '', False, ''),
    ('full-leg-wax', 'Full leg wax', '900.00', 60, '', False, ''),
]

LASER_TREATMENTS = [
    ('laser-upper-lip', 'Upper lip', '150.00', 15, '', False, ''),
    ('laser-chin', 'Chin', '250.00', 15, '', False, ''),
    ('laser-neck', 'Neck', '350.00', 20, '', False, ''),
    ('laser-lower-face', 'Lower face', '500.00', 30, '', False, ''),
    ('laser-full-face', 'Full face', '600.00', 45, '', False, ''),
    ('laser-chest', 'Chest', '500.00', 30, '', False, ''),
    ('laser-tummy-line', 'Tummy line', '300.00', 20, '', False, ''),
    ('laser-full-tummy', 'Full tummy', '600.00', 35, '', False, ''),
    ('laser-underarms', 'Underarms', '500.00', 25, '', False, ''),
    ('laser-full-arms', 'Full arms', '900.00', 50, '', False, ''),
    ('laser-full-back', 'Full back', '1000.00', 60, '', False, ''),
    ('laser-brazilian', 'Brazilian', '500.00', 35, '', False, ''),
    ('laser-hollywood', 'Hollywood', '680.00', 45, '', False, ''),
    ('laser-buttocks', 'Buttocks', '600.00', 35, '', False, ''),
    ('laser-half-leg', 'Half leg', '800.00', 45, '', False, ''),
    ('laser-full-leg', 'Full leg', '1400.00', 75, '', False, ''),
]

TREATMENTS_BY_SERVICE = {
    'nail-treatment': NAIL_TREATMENTS,
    'massage-therapy': MASSAGE_TREATMENTS,
    'facial-treatment': FACIAL_TREATMENTS,
    'waxing-treatments': WAXING_TREATMENTS,
    'laser-treatments': LASER_TREATMENTS,
}

# Waxing add-on section links to facial treatments (canonical rows).
WAXING_ADDON_SLUGS = ('vajacial', 'eyebrow-tint', 'eyebrow-lamination')

STAFF = [
    (
        'grace',
        'Grace M.',
        'Facials & peels',
        'facial-treatment',
    ),
    (
        'tendai',
        'Tendai K.',
        'Massage therapy',
        'massage-therapy',
    ),
    (
        'nomsa',
        'Nomsa B.',
        'Nails & waxing',
        ('nail-treatment', 'waxing-treatments'),
    ),
    (
        'chanda',
        'Chanda L.',
        'Laser specialist',
        'laser-treatments',
    ),
]

WORK_DAYS = (
    DayOfWeek.MONDAY,
    DayOfWeek.TUESDAY,
    DayOfWeek.WEDNESDAY,
    DayOfWeek.THURSDAY,
    DayOfWeek.FRIDAY,
    DayOfWeek.SATURDAY,
)


class Command(BaseCommand):
    help = 'Seed services, treatments, staff, and weekly availability.'

    def handle(self, *args, **options):
        service_map = {}
        for slug, name, description, tagline, sort_order in SERVICES:
            service, _ = Service.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'description': description,
                    'tagline': tagline,
                    'sort_order': sort_order,
                    'is_active': True,
                },
            )
            service_map[slug] = service

        treatment_map = {}
        for service_slug, rows in TREATMENTS_BY_SERVICE.items():
            service = service_map[service_slug]
            for slug, tname, price, duration, subsection, price_from, price_label in rows:
                treatment, _ = Treatment.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'service': service,
                        'name': tname,
                        'duration_minutes': duration,
                        'price': price,
                        'subsection': subsection,
                        'price_from': price_from,
                        'price_label': price_label,
                        'is_active': True,
                    },
                )
                treatment_map[slug] = treatment

        for username, display_name, specialization, service_slugs in STAFF:
            if isinstance(service_slugs, str):
                service_slugs = (service_slugs,)

            user, _ = User.objects.get_or_create(
                username=f'staff_{username}',
                defaults={'email': f'{username}@skinsensation.local'},
            )
            staff, _ = Staff.objects.update_or_create(
                user=user,
                defaults={
                    'display_name': display_name,
                    'specialization': specialization,
                    'is_available': True,
                },
            )
            treatment_pks = [
                t.pk
                for slug, t in treatment_map.items()
                if t.service.slug in service_slugs
            ]
            staff.treatments.set(treatment_pks)

            for day in WORK_DAYS:
                StaffAvailability.objects.update_or_create(
                    staff=staff,
                    day_of_week=day,
                    defaults={
                        'start_time': time(9, 0),
                        'end_time': time(18, 0),
                        'is_off_day': False,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(service_map)} services and {len(treatment_map)} treatments.'
        ))
