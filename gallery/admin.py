from django.contrib import admin

from gallery.models import GalleryImage


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('caption', 'category', 'layout', 'sort_order', 'is_active', 'created_at')
    list_filter = ('category', 'is_active', 'layout')
    search_fields = ('caption', 'alt_text')
    ordering = ('sort_order', '-created_at')
