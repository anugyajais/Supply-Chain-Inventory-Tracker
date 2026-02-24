from django.db import models

# Create your models here.
"""
Order management models for purchase orders, transfers, and sales.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


# ============================================================================
# PURCHASE ORDERS
# ============================================================================

class PurchaseOrder(models.Model):
    """
    Purchase Order - ordering products from suppliers.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Auto-generated PO number
    po_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Auto-generated: PO-YYYY-XXXX"
    )
    
    # Supplier and destination
    supplier = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        limit_choices_to={'location_type': 'supplier'},
        related_name='purchase_orders'
    )
    destination = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        limit_choices_to={'location_type__in': ['warehouse', 'distribution']},
        related_name='incoming_purchase_orders',
        help_text="Warehouse receiving the shipment"
    )
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)]
    )
    
    # Dates
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Additional info
    notes = models.TextField(blank=True)
    
    # User tracking
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_purchase_orders'
    )
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_purchase_orders'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['po_number']),
            models.Index(fields=['status']),
            models.Index(fields=['supplier']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
    
    def __str__(self):
        return f"{self.po_number} - {self.supplier.name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.po_number:
            # Generate PO number: PO-2024-0001
            from django.utils import timezone
            year = timezone.now().year
            last_po = PurchaseOrder.objects.filter(
                po_number__startswith=f'PO-{year}'
            ).order_by('po_number').last()
            
            if last_po:
                last_num = int(last_po.po_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.po_number = f'PO-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Calculate total from all items"""
        total = self.items.aggregate(
            total=models.Sum(models.F('ordered_quantity') * models.F('unit_cost'))
        )['total'] or Decimal('0.00')
        return total
    
    def update_total(self):
        """Update total_amount field"""
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount'])


class PurchaseOrderItem(models.Model):
    """
    Line items in a purchase order.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('complete', 'Complete'),
    ]
    
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    
    # Quantities
    ordered_quantity = models.IntegerField(validators=[MinValueValidator(1)])
    received_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Pricing
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'
    
    def __str__(self):
        return f"{self.product.name} x {self.ordered_quantity}"
    
    @property
    def line_total(self):
        """Calculate line total"""
        return self.ordered_quantity * self.unit_cost
    
    def clean(self):
        """Validate received quantity"""
        if self.received_quantity > self.ordered_quantity:
            raise ValidationError("Received quantity cannot exceed ordered quantity")
    
    def save(self, *args, **kwargs):
        # Update status based on received quantity
        if self.received_quantity == 0:
            self.status = 'pending'
        elif self.received_quantity < self.ordered_quantity:
            self.status = 'partial'
        elif self.received_quantity == self.ordered_quantity:
            self.status = 'complete'
        
        super().save(*args, **kwargs)


class PurchaseOrderReceipt(models.Model):
    """
    Receipt record when shipment arrives.
    One PO can have multiple receipts (partial shipments).
    """
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )
    
    received_at = models.DateTimeField()
    received_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_pos'
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Purchase Order Receipt'
        verbose_name_plural = 'Purchase Order Receipts'
    
    def __str__(self):
        return f"{self.receipt_number} - {self.purchase_order.po_number}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            from django.utils import timezone
            year = timezone.now().year
            last_receipt = PurchaseOrderReceipt.objects.filter(
                receipt_number__startswith=f'REC-{year}'
            ).order_by('receipt_number').last()
            
            if last_receipt:
                last_num = int(last_receipt.receipt_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.receipt_number = f'REC-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)


class PurchaseOrderReceiptItem(models.Model):
    """
    Items in a receipt - what was actually received.
    """
    CONDITION_CHOICES = [
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('rejected', 'Rejected'),
    ]
    
    receipt = models.ForeignKey(
        PurchaseOrderReceipt,
        on_delete=models.CASCADE,
        related_name='items'
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.CASCADE,
        related_name='receipt_items'
    )
    
    quantity_received = models.IntegerField(validators=[MinValueValidator(0)])
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Receipt Item'
        verbose_name_plural = 'Receipt Items'
    
    def __str__(self):
        return f"{self.purchase_order_item.product.name} x {self.quantity_received} ({self.condition})"


# ============================================================================
# TRANSFER ORDERS
# ============================================================================

class TransferOrder(models.Model):
    """
    Internal transfer of inventory between locations.
    """
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('in_transit', 'In Transit'),
        ('received', 'Received'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('urgent', 'Urgent'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]
    
    transfer_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )
    
    # Locations
    from_location = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        related_name='outgoing_transfers'
    )
    to_location = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        related_name='incoming_transfers'
    )
    route = models.ForeignKey(
        'network.ShippingRoute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfers'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Dates
    expected_arrival_date = models.DateField(null=True, blank=True)
    actual_arrival_date = models.DateField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    
    # Users
    requested_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_transfers'
    )
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transfers'
    )
    
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transfer_number']),
            models.Index(fields=['status']),
            models.Index(fields=['from_location', 'to_location']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Transfer Order'
        verbose_name_plural = 'Transfer Orders'
    
    def __str__(self):
        return f"{self.transfer_number} - {self.from_location.name} → {self.to_location.name}"
    
    def save(self, *args, **kwargs):
        if not self.transfer_number:
            from django.utils import timezone
            year = timezone.now().year
            last_transfer = TransferOrder.objects.filter(
                transfer_number__startswith=f'TRF-{year}'
            ).order_by('transfer_number').last()
            
            if last_transfer:
                last_num = int(last_transfer.transfer_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.transfer_number = f'TRF-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate from_location != to_location"""
        if self.from_location == self.to_location:
            raise ValidationError("Cannot transfer to the same location")


class TransferOrderItem(models.Model):
    """
    Items in a transfer order.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('received', 'Received'),
    ]
    
    transfer_order = models.ForeignKey(
        TransferOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='transfer_items'
    )
    
    requested_quantity = models.IntegerField(validators=[MinValueValidator(1)])
    shipped_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    received_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Transfer Order Item'
        verbose_name_plural = 'Transfer Order Items'
    
    def __str__(self):
        return f"{self.product.name} x {self.requested_quantity}"
    
    def clean(self):
        if self.shipped_quantity > self.requested_quantity:
            raise ValidationError("Shipped quantity cannot exceed requested quantity")
        if self.received_quantity > self.shipped_quantity:
            raise ValidationError("Received quantity cannot exceed shipped quantity")


# ============================================================================
# SALES ORDERS
# ============================================================================

class SalesOrder(models.Model):
    """
    Customer sales orders - products leaving stores.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('partially_fulfilled', 'Partially Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]
    
    order_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )
    
    # Store location
    store = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        limit_choices_to={'location_type': 'store'},
        related_name='sales_orders'
    )
    
    # Customer info
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    
    # Status and totals
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Dates
    order_date = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
            models.Index(fields=['store']),
            models.Index(fields=['-order_date']),
        ]
        verbose_name = 'Sales Order'
        verbose_name_plural = 'Sales Orders'
    
    def __str__(self):
        return f"{self.order_number} - {self.store.name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            from django.utils import timezone
            year = timezone.now().year
            last_order = SalesOrder.objects.filter(
                order_number__startswith=f'SO-{year}'
            ).order_by('order_number').last()
            
            if last_order:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.order_number = f'SO-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Calculate total from items"""
        total = self.items.aggregate(
            total=models.Sum(models.F('quantity_ordered') * models.F('unit_price'))
        )['total'] or Decimal('0.00')
        return total
    
    def update_total(self):
        """Update total_amount field"""
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount'])


class SalesOrderItem(models.Model):
    """
    Line items in a sales order.
    """
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='sales_order_items'
    )
    
    quantity_ordered = models.IntegerField(validators=[MinValueValidator(1)])
    quantity_fulfilled = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Sales Order Item'
        verbose_name_plural = 'Sales Order Items'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity_ordered}"
    
    @property
    def line_total(self):
        return self.quantity_ordered * self.unit_price
    
    def clean(self):
        if self.quantity_fulfilled > self.quantity_ordered:
            raise ValidationError("Fulfilled quantity cannot exceed ordered quantity")


class BackOrder(models.Model):
    """
    Tracks items that couldn't be fulfilled due to insufficient stock.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]
    
    sales_order_item = models.ForeignKey(
        SalesOrderItem,
        on_delete=models.CASCADE,
        related_name='backorders'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='backorders'
    )
    location = models.ForeignKey(
        'network.Location',
        on_delete=models.PROTECT,
        related_name='backorders'
    )
    
    quantity_backordered = models.IntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    expected_fulfillment_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['product', 'location']),
        ]
        verbose_name = 'Back Order'
        verbose_name_plural = 'Back Orders'
    
    def __str__(self):
        return f"Backorder: {self.product.name} x {self.quantity_backordered} @ {self.location.name}"