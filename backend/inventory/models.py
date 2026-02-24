from django.db import models

# Create your models here.
"""
Inventory models for products and stock management.
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Product(models.Model):
    """
    Product catalog - stores all products available in the system.
    """
    sku = models.CharField(
        max_length=50,
        unique=True,
        help_text="Stock Keeping Unit - unique product identifier"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    
    # Physical specifications
    unit_of_measure = models.CharField(
        max_length=20,
        default='pieces',
        help_text="e.g., pieces, kg, liters, boxes"
    )
    weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    dimensions_cm = models.CharField(
        max_length=50,
        blank=True,
        help_text="Format: LxWxH (e.g., 30x20x10)"
    )
    
    # Cost (average across suppliers)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
    
    def __str__(self):
        return f"{self.sku} - {self.name}"
    
    def get_total_inventory(self):
        """Get total inventory across all locations"""
        return self.inventory_levels.aggregate(
            total=models.Sum('quantity_on_hand')
        )['total'] or 0


class ProductSupplier(models.Model):
    """
    Many-to-Many relationship between Products and Suppliers.
    Stores supplier-specific information like cost and lead time.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='suppliers'
    )
    supplier = models.ForeignKey(
        'network.Location',
        on_delete=models.CASCADE,
        limit_choices_to={'location_type': 'supplier'},
        related_name='supplied_products'
    )
    
    # Supplier-specific details
    supplier_sku = models.CharField(
        max_length=100,
        blank=True,
        help_text="Supplier's internal product code"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    lead_time_days = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Days from order to delivery"
    )
    minimum_order_quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Minimum quantity that can be ordered"
    )
    
    # Preferences
    is_preferred = models.BooleanField(
        default=False,
        help_text="Preferred supplier for this product"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['product', 'supplier']
        ordering = ['-is_preferred', 'unit_cost']
        indexes = [
            models.Index(fields=['product', 'supplier']),
            models.Index(fields=['is_preferred']),
        ]
        verbose_name = 'Product Supplier'
        verbose_name_plural = 'Product Suppliers'
    
    def __str__(self):
        preferred = " ⭐" if self.is_preferred else ""
        return f"{self.product.name} from {self.supplier.name}{preferred}"

    # Add this to the same file after ProductSupplier

class InventoryLevel(models.Model):
    """
    Tracks inventory quantity for each product at each location.
    This is the core table - one row per product per location.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory_levels'
    )
    location = models.ForeignKey(
        'network.Location',
        on_delete=models.CASCADE,
        related_name='inventory_levels'
    )
    
    # Quantity tracking
    quantity_on_hand = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Physical quantity in stock"
    )
    quantity_reserved = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Quantity allocated for pending orders"
    )
    quantity_incoming = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Quantity expected from POs/transfers"
    )
    
    # Reorder intelligence
    reorder_point = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Trigger reorder when stock falls below this"
    )
    safety_stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Buffer stock to prevent stockouts"
    )
    max_stock = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Maximum stock level (optional)"
    )
    
    # Tracking
    last_counted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last physical inventory count"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['product', 'location']
        ordering = ['location', 'product']
        indexes = [
            models.Index(fields=['product', 'location']),
            models.Index(fields=['quantity_on_hand']),
            models.Index(fields=['location']),
        ]
        verbose_name = 'Inventory Level'
        verbose_name_plural = 'Inventory Levels'
    
    def __str__(self):
        return f"{self.product.name} @ {self.location.name}: {self.quantity_on_hand}"
    
    @property
    def quantity_available(self):
        """Calculate available quantity (on_hand - reserved)"""
        return max(0, self.quantity_on_hand - self.quantity_reserved)
    
    @property
    def needs_reorder(self):
        """Check if inventory is below reorder point"""
        return self.quantity_on_hand < self.reorder_point
    
    def get_status(self):
        """Return inventory status"""
        if self.quantity_on_hand == 0:
            return 'out_of_stock'
        elif self.needs_reorder:
            return 'low_stock'
        elif self.max_stock and self.quantity_on_hand > self.max_stock:
            return 'overstock'
        return 'ok'


class StockMovement(models.Model):
    """
    Audit trail of all inventory changes.
    Every inventory update creates a StockMovement record.
    """
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase Receipt'),
        ('sale', 'Sale'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('adjustment', 'Inventory Adjustment'),
        ('return', 'Return'),
        ('damage', 'Damage/Loss'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    location = models.ForeignKey(
        'network.Location',
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    
    # Movement details
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(
        help_text="Positive for additions, negative for deductions"
    )
    
    # Reference to source document
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., PurchaseOrder, TransferOrder, SalesOrder"
    )
    reference_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="ID of the source document"
    )
    
    # Additional info
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    
    # Timestamp (no updated_at - movements are immutable)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'location']),
            models.Index(fields=['movement_type']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
    
    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.quantity:+d} {self.product.name} @ {self.location.name}"


class DemandHistory(models.Model):
    """
    Tracks historical demand (sales) for reorder point calculations.
    One record per product per location per day.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='demand_history'
    )
    location = models.ForeignKey(
        'network.Location',
        on_delete=models.CASCADE,
        related_name='demand_history'
    )
    
    date = models.DateField()
    quantity_sold = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['product', 'location', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['product', 'location', '-date']),
        ]
        verbose_name = 'Demand History'
        verbose_name_plural = 'Demand History'
    
    def __str__(self):
        return f"{self.product.name} @ {self.location.name} on {self.date}: {self.quantity_sold}"


class ReorderAlert(models.Model):
    """
    Alerts when inventory falls below reorder point.
    Generated automatically by Celery task.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('acknowledged', 'Acknowledged'),
        ('ordered', 'Order Placed'),
        ('dismissed', 'Dismissed'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reorder_alerts'
    )
    location = models.ForeignKey(
        'network.Location',
        on_delete=models.CASCADE,
        related_name='reorder_alerts'
    )
    
    # Alert details
    current_stock = models.IntegerField()
    reorder_point = models.IntegerField()
    suggested_order_quantity = models.IntegerField(null=True, blank=True)
    
    # Supplier suggestion
    supplier = models.ForeignKey(
        'network.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'location_type': 'supplier'},
        related_name='suggested_reorders'
    )
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    acknowledged_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['product', 'location']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Reorder Alert'
        verbose_name_plural = 'Reorder Alerts'
    
    def __str__(self):
        return f"Alert: {self.product.name} @ {self.location.name} ({self.status})"
    
    @property
    def shortage_quantity(self):
        """Calculate how much below reorder point"""
        return max(0, self.reorder_point - self.current_stock)