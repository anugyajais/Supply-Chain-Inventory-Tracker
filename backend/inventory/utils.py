"""
Core inventory management utility functions.
These handle all inventory updates with atomic transactions.
"""
from django.db import transaction
from django.utils import timezone
from .models import InventoryLevel, StockMovement
from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Avg


@transaction.atomic
def update_inventory(product, location, quantity, movement_type, 
                    reference_type=None, reference_id=None, user=None, notes=''):
    """
    Atomically update inventory and create audit trail.
    
    Args:
        product: Product instance
        location: Location instance
        quantity: Integer (positive for additions, negative for deductions)
        movement_type: String (purchase, sale, transfer_in, transfer_out, adjustment)
        reference_type: String (optional - e.g., 'PurchaseOrder')
        reference_id: Integer (optional - ID of source document)
        user: User instance (optional)
        notes: String (optional)
    
    Returns:
        InventoryLevel instance
    
    Raises:
        ValueError: If insufficient stock for deduction
    """
    # Lock the inventory record to prevent race conditions
    inventory, created = InventoryLevel.objects.select_for_update().get_or_create(
        product=product,
        location=location,
        defaults={'quantity_on_hand': 0}
    )
    
    # Calculate new quantity
    new_quantity = inventory.quantity_on_hand + quantity
    
    # Validate sufficient stock for deductions
    if new_quantity < 0:
        available = inventory.quantity_on_hand
        required = abs(quantity)
        raise ValueError(
            f"Insufficient stock for {product.name} at {location.name}. "
            f"Available: {available}, Required: {required}"
        )
    
    # Update inventory
    inventory.quantity_on_hand = new_quantity
    inventory.save()
    
    # Create audit trail
    movement = StockMovement.objects.create(
        product=product,
        location=location,
        movement_type=movement_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        created_by=user,
        notes=notes
    )
    
    return inventory


def get_available_quantity(product, location):
    """
    Get available quantity (on_hand - reserved).
    
    Returns:
        Integer: Available quantity
    """
    try:
        inventory = InventoryLevel.objects.get(product=product, location=location)
        return inventory.quantity_available
    except InventoryLevel.DoesNotExist:
        return 0


def reserve_inventory(product, location, quantity):
    """
    Reserve inventory for an order (doesn't deduct, just reserves).
    
    Args:
        product: Product instance
        location: Location instance
        quantity: Integer to reserve
    
    Returns:
        InventoryLevel instance
    
    Raises:
        ValueError: If insufficient available stock
    """
    inventory = InventoryLevel.objects.select_for_update().get(
        product=product,
        location=location
    )
    
    available = inventory.quantity_available
    if available < quantity:
        raise ValueError(
            f"Insufficient available stock. Available: {available}, Requested: {quantity}"
        )
    
    inventory.quantity_reserved += quantity
    inventory.save()
    
    return inventory


def release_reservation(product, location, quantity):
    """
    Release reserved inventory (e.g., when order is cancelled).
    """
    inventory = InventoryLevel.objects.select_for_update().get(
        product=product,
        location=location
    )
    
    inventory.quantity_reserved = max(0, inventory.quantity_reserved - quantity)
    inventory.save()
    
    return inventory


def adjust_inventory(product, location, new_quantity, user, reason=''):
    """
    Manual inventory adjustment (e.g., after physical count).
    
    Args:
        product: Product instance
        location: Location instance
        new_quantity: Integer - the corrected quantity
        user: User instance
        reason: String - reason for adjustment
    
    Returns:
        InventoryLevel instance
    """
    inventory = InventoryLevel.objects.get(product=product, location=location)
    old_quantity = inventory.quantity_on_hand
    difference = new_quantity - old_quantity
    
    if difference != 0:
        update_inventory(
            product=product,
            location=location,
            quantity=difference,
            movement_type='adjustment',
            user=user,
            notes=f"Adjustment: {old_quantity} → {new_quantity}. Reason: {reason}"
        )
    
    # Update last counted
    inventory.last_counted_at = timezone.now()
    inventory.save()
    
    return inventory


def get_inventory_value(location=None):
    """
    Calculate total inventory value.
    
    Args:
        location: Location instance (optional - if None, calculates for all locations)
    
    Returns:
        Decimal: Total inventory value
    """
    from django.db.models import F, Sum
    
    queryset = InventoryLevel.objects.all()
    if location:
        queryset = queryset.filter(location=location)
    
    total = queryset.annotate(
        value=F('quantity_on_hand') * F('product__unit_cost')
    ).aggregate(
        total_value=Sum('value')
    )['total_value'] or Decimal('0.00')
    
    return total

def calculate_reorder_point(product, location, lookback_days=30):
    """
    Calculate reorder point based on historical demand.
    
    Formula: (Average Daily Demand × Lead Time) + Safety Stock
    
    Args:
        product: Product instance
        location: Location instance
        lookback_days: Number of days to analyze (default 30)
    
    Returns:
        Tuple: (reorder_point, safety_stock)
    """
    from datetime import timedelta
    from django.utils import timezone
    
    # Get historical demand
    start_date = timezone.now().date() - timedelta(days=lookback_days)
    
    demand_records = DemandHistory.objects.filter(
        product=product,
        location=location,
        date__gte=start_date
    )
    
    total_demand = demand_records.aggregate(
        total=Sum('quantity_sold')
    )['total'] or 0
    
    # Calculate average daily demand
    avg_daily_demand = total_demand / lookback_days if lookback_days > 0 else 0
    
    # Get lead time from preferred supplier
    try:
        from inventory.models import ProductSupplier
        supplier = ProductSupplier.objects.filter(
            product=product,
            is_preferred=True
        ).first()
        
        if not supplier:
            supplier = ProductSupplier.objects.filter(product=product).first()
        
        lead_time_days = supplier.lead_time_days if supplier else 7
    except:
        lead_time_days = 7  # Default fallback
    
    # Calculate safety stock (1 week of average demand as buffer)
    safety_stock = int(avg_daily_demand * 7)
    
    # Calculate reorder point
    reorder_point = int((avg_daily_demand * lead_time_days) + safety_stock)
    
    return reorder_point, safety_stock


def calculate_suggested_order_quantity(product, location, lookback_days=30):
    """
    Calculate suggested order quantity.
    Simple approach: 30 days of average demand.
    
    Returns:
        Integer: Suggested order quantity
    """
    from datetime import timedelta
    from django.utils import timezone
    
    start_date = timezone.now().date() - timedelta(days=lookback_days)
    
    total_demand = DemandHistory.objects.filter(
        product=product,
        location=location,
        date__gte=start_date
    ).aggregate(total=Sum('quantity_sold'))['total'] or 0
    
    avg_daily_demand = total_demand / lookback_days
    order_qty = int(avg_daily_demand * 30)  # 1 month supply
    
    return max(order_qty, 1)  # At least 1


def get_low_stock_items(location=None, threshold_percentage=1.0):
    """
    Get all items that are below reorder point.
    
    Args:
        location: Location instance (optional)
        threshold_percentage: Float (1.0 = at reorder point, 0.8 = 80% of reorder point)
    
    Returns:
        QuerySet of InventoryLevel instances
    """
    from django.db.models import F
    
    queryset = InventoryLevel.objects.select_related('product', 'location')
    
    if location:
        queryset = queryset.filter(location=location)
    
    # Filter where quantity_on_hand < (reorder_point * threshold)
    low_stock = queryset.annotate(
        threshold=F('reorder_point') * threshold_percentage
    ).filter(
        quantity_on_hand__lt=F('threshold'),
        reorder_point__gt=0  # Only items with reorder point set
    )
    
    return low_stock