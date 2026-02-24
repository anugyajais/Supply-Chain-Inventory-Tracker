from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Location, ShippingRoute


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'location_type', 'city', 'is_active', 'created_at']
    list_filter = ['location_type', 'is_active', 'country']
    search_fields = ['name', 'city', 'manager_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'location_type', 'is_active')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Management', {
            'fields': ('capacity', 'manager_name', 'manager_email', 'manager_phone')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ShippingRoute)
class ShippingRouteAdmin(admin.ModelAdmin):
    list_display = ['from_location', 'to_location', 'average_lead_time_days', 'shipping_cost_per_unit', 'is_active']
    list_filter = ['is_active']
    search_fields = ['from_location__name', 'to_location__name']
    readonly_fields = ['created_at', 'updated_at']