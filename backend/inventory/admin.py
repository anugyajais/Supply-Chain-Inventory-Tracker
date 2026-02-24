from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Product, ProductSupplier, InventoryLevel,
    StockMovement, DemandHistory, ReorderAlert
)


class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'unit_cost', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['sku', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProductSupplierInline]


@admin.register(InventoryLevel)
class InventoryLevelAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'location', 'quantity_on_hand', 
        'quantity_available', 'quantity_incoming', 'needs_reorder'
    ]
    list_filter = ['location', 'location__location_type']
    search_fields = ['product__name', 'product__sku', 'location__name']
    readonly_fields = ['created_at', 'updated_at', 'quantity_available']
    
    def quantity_available(self, obj):
        return obj.quantity_available
    quantity_available.short_description = 'Available'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'movement_type', 'quantity', 'created_at']
    list_filter = ['movement_type', 'location']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(ReorderAlert)
class ReorderAlertAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'location', 'current_stock', 
        'reorder_point', 'status', 'created_at'
    ]
    list_filter = ['status', 'location']
    search_fields = ['product__name', 'product__sku']
    readonly_fields = ['created_at', 'shortage_quantity']
    
    def shortage_quantity(self, obj):
        return obj.shortage_quantity
    shortage_quantity.short_description = 'Shortage'


@admin.register(DemandHistory)
class DemandHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'location', 'date', 'quantity_sold']
    list_filter = ['location', 'date']
    search_fields = ['product__name']
    date_hierarchy = 'date'