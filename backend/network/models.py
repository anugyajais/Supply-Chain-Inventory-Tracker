from django.db import models

# Create your models here.
"""
Network models for managing supply chain locations and routes.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Location(models.Model):
    """
    Represents a location in the supply chain network.
    Can be: Supplier, Warehouse, Distribution Center, or Store.
    """
    LOCATION_TYPES = [
        ('supplier', 'Supplier'),
        ('warehouse', 'Warehouse'),
        ('distribution', 'Distribution Center'),
        ('store', 'Store'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES)
    
    # Address information
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='USA')
    
    # Capacity and management
    capacity = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum storage capacity (optional)"
    )
    manager_name = models.CharField(max_length=200, blank=True)
    manager_email = models.EmailField(blank=True)
    manager_phone = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['location_type', 'name']
        indexes = [
            models.Index(fields=['location_type']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
    
    def __str__(self):
        return f"{self.name} ({self.get_location_type_display()})"
    
    def get_full_address(self):
        """Return formatted address"""
        parts = [self.address, self.city, self.state, self.postal_code, self.country]
        return ', '.join([p for p in parts if p])
    
    def is_supplier(self):
        return self.location_type == 'supplier'
    
    def is_warehouse(self):
        return self.location_type == 'warehouse'
    
    def is_store(self):
        return self.location_type == 'store'


class ShippingRoute(models.Model):
    """
    Represents a shipping route between two locations.
    Stores lead time and cost information.
    """
    from_location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='outgoing_routes'
    )
    to_location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='incoming_routes'
    )
    
    # Route details
    average_lead_time_days = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Average shipping time in days"
    )
    shipping_cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Cost per unit shipped"
    )
    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['from_location', 'to_location']
        ordering = ['from_location', 'to_location']
        indexes = [
            models.Index(fields=['from_location', 'to_location']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'Shipping Route'
        verbose_name_plural = 'Shipping Routes'
    
    def __str__(self):
        return f"{self.from_location.name} → {self.to_location.name} ({self.average_lead_time_days}d)"
    
    def clean(self):
        """Validate that from_location != to_location"""
        if self.from_location == self.to_location:
            raise ValidationError("Cannot create route from a location to itself")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)