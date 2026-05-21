from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from services.constants import EXCLUDED_SERVICE_SLUGS
from services.models import Service, Treatment
from services.selectors import (
    apply_sort,
    category_choices,
    filter_services,
    filter_treatments,
)


class SelectorTestMixin:
    @classmethod
    def setUpTestData(cls):
        cls.facial = Service.objects.create(
            slug='facial-treatment',
            name='Facial Treatment',
            description='Glow facials',
            tagline='Glow',
            sort_order=1,
            is_active=True,
        )
        cls.massage = Service.objects.create(
            slug='massage-therapy',
            name='Massage Therapy',
            description='Relaxing massage',
            sort_order=2,
            is_active=True,
        )
        _excluded_slug = next(iter(sorted(EXCLUDED_SERVICE_SLUGS)))
        cls.excluded = Service.objects.create(
            slug=_excluded_slug,
            name='Add-On',
            is_active=True,
        )
        cls.inactive_service = Service.objects.create(
            slug='inactive-group',
            name='Inactive',
            is_active=False,
        )

        cls.facial_basic = Treatment.objects.create(
            service=cls.facial,
            slug='express-facial',
            name='Express Facial',
            description='Quick refresh facial',
            duration_minutes=30,
            price=Decimal('300.00'),
            sort_order=1,
            is_active=True,
        )
        cls.facial_deep = Treatment.objects.create(
            service=cls.facial,
            slug='deep-cleansing',
            name='Deep Cleansing Facial',
            description='Thorough cleanse',
            duration_minutes=60,
            price=Decimal('500.00'),
            sort_order=2,
            is_featured=True,
            is_active=True,
        )
        cls.massage_swedish = Treatment.objects.create(
            service=cls.massage,
            slug='swedish-massage',
            name='Swedish Massage',
            description='Classic relaxation',
            duration_minutes=60,
            price=Decimal('400.00'),
            sort_order=1,
            is_active=True,
        )
        Treatment.objects.create(
            service=cls.excluded,
            slug='addon-item',
            name='Addon Item',
            duration_minutes=15,
            price=Decimal('50.00'),
            is_active=True,
        )
        Treatment.objects.create(
            service=cls.facial,
            slug='inactive-treatment',
            name='Inactive Facial',
            duration_minutes=30,
            price=Decimal('100.00'),
            is_active=False,
        )


class FilterTreatmentsTests(SelectorTestMixin, TestCase):
    def test_returns_only_active_from_active_services(self):
        names = list(filter_treatments().values_list('name', flat=True))
        self.assertIn('Express Facial', names)
        self.assertNotIn('Inactive Facial', names)
        self.assertNotIn('Addon Item', names)

    def test_search_matches_name(self):
        qs = filter_treatments(search='swedish')
        self.assertEqual(list(qs), [self.massage_swedish])

    def test_search_matches_description(self):
        qs = filter_treatments(search='refresh')
        self.assertEqual(list(qs), [self.facial_basic])

    def test_category_slug_filter(self):
        qs = filter_treatments(category_slug='facial-treatment')
        self.assertEqual(qs.count(), 2)
        self.assertTrue(all(t.service_id == self.facial.id for t in qs))

    def test_service_slug_alias(self):
        qs = filter_treatments(service_slug='massage-therapy')
        self.assertEqual(qs.count(), 1)

    def test_sort_price_low(self):
        qs = filter_treatments(category_slug='facial-treatment', sort='price_low')
        prices = list(qs.values_list('price', flat=True))
        self.assertEqual(prices, sorted(prices))

    def test_sort_price_high(self):
        qs = filter_treatments(category_slug='facial-treatment', sort='price_high')
        prices = list(qs.values_list('price', flat=True))
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_sort_featured_first(self):
        qs = filter_treatments(category_slug='facial-treatment', sort='featured')
        self.assertEqual(qs.first(), self.facial_deep)

    def test_excluded_service_slugs_never_appear(self):
        for slug in EXCLUDED_SERVICE_SLUGS:
            self.assertNotIn(
                slug,
                filter_treatments().values_list('service__slug', flat=True),
            )


class FilterServicesTests(SelectorTestMixin, TestCase):
    def test_excludes_hidden_slugs(self):
        slugs = list(filter_services().values_list('slug', flat=True))
        self.assertIn('facial-treatment', slugs)
        self.assertNotIn(self.excluded.slug, slugs)

    def test_search_matches_tagline(self):
        qs = filter_services(search='Glow')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.facial)

    def test_category_slug_narrows_hub(self):
        qs = filter_services(category_slug='massage-therapy')
        self.assertEqual(qs.count(), 1)


class CategoryChoicesTests(SelectorTestMixin, TestCase):
    def test_returns_active_non_excluded(self):
        slugs = list(category_choices().values_list('slug', flat=True))
        self.assertIn('facial-treatment', slugs)
        self.assertNotIn(self.excluded.slug, slugs)


class ApplySortTests(SelectorTestMixin, TestCase):
    def test_default_ordering(self):
        qs = apply_sort(filter_treatments(), None)
        self.assertGreaterEqual(qs.count(), 1)


class CatalogApiTests(SelectorTestMixin, TestCase):
    def setUp(self):
        self.client = Client()

    def test_catalog_search_filters_json(self):
        url = reverse('services:service_list')
        response = self.client.get(url, {'search': 'swedish'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Swedish Massage')

    def test_catalog_service_slug_filter(self):
        url = reverse('services:service_list')
        response = self.client.get(url, {'service': 'facial-treatment'})
        self.assertEqual(response.status_code, 200)
        names = {item['name'] for item in response.json()}
        self.assertIn('Express Facial', names)
        self.assertNotIn('Swedish Massage', names)
