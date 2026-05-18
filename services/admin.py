from django.contrib import admin

from .models import Service, Treatment


class TreatmentInline(admin.TabularInline):
    model = Treatment
    extra = 0
    fields = ('name', 'slug', 'price', 'duration_minutes', 'subsection', 'is_active', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TreatmentInline]


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'service',
        'duration_minutes',
        'price',
        'subsection',
        'is_active',
    )
    list_filter = ('service', 'subsection', 'is_active', 'is_featured')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
