"""
Order workflow functions for purchase orders, transfers, and sales.
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from inventory.utils import update_inventory
from inventory.models import DemandHistory
from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, PurchaseOrderReceiptItem,
    TransferOrder, TransferOrderItem,
    SalesOrder, SalesOrderItem, BackOrder
)


# ============================================================================
# PURCHASE ORDER WORKFLOWS
# ============================================================================

@transaction.atomic
def confirm_purchase_order(purchase_order, user=None):
    """
    Confirm a purchase order (change status from draft to confirmed).
    Updates incoming quantities for destination warehouse.
    """
    if purchase_order.status != 'draft':
        raise ValidationError(f"Cannot confirm PO with status: {purchase_order.status}")
    
    # Update incoming quantities
    for item in purchase_order.items.all():
        inventory, _ = InventoryLevel.objects.get_or_create(
            product=item.product,
            location=purchase_order.destination
        )
        inventory.quantity_incoming += item.ordered_quantity
        inventory.save()
    
    # Update PO status
    purchase_order.status = 'confirmed'
    purchase_order.approved_by = user
    purchase_order.save()
    
    return purchase_order


@transaction.atomic
def receive_purchase_order(purchase_order, receipt_data, user=None):
    """
    Receive a purchase order shipment.
    
    Args:
        purchase_order: PurchaseOrder instance
        receipt_data: Dict with structure:
            {
                'received_at': datetime,
                'notes': str,
                'items': [
                    {
                        'purchase_order_item_id': int,
                        'quantity_received': int,
                        'condition': str ('good', 'damaged', 'rejected')
                    },
                    ...
                ]
            }
        user: User instance
    
    Returns:
        PurchaseOrderReceipt instance
    """
    if purchase_order.status not in ['confirmed', 'shipped']:
        raise ValidationError(f"Cannot receive PO with status: {purchase_order.status}")
    
    # Create receipt
    receipt = PurchaseOrderReceipt.objects.create(
        purchase_order=purchase_order,
        received_at=receipt_data.get('received_at', timezone.now()),
        received_by=user,
        notes=receipt_data.get('notes', '')
    )
    
    # Process each item
    for item_data in receipt_data.get('items', []):
        po_item = PurchaseOrderItem.objects.select_for_update().get(
            id=item_data['purchase_order_item_id']
        )
        
        qty_received = item_data['quantity_received']
        condition = item_data.get('condition', 'good')
        
        # Create receipt item
        receipt_item = PurchaseOrderReceiptItem.objects.create(
            receipt=receipt,
            purchase_order_item=po_item,
            quantity_received=qty_received,
            condition=condition,
            notes=item_data.get('notes', '')
        )
        
        # Only update inventory for items in good condition
        if condition == 'good' and qty_received > 0:
            # Update inventory (adds to stock)
            update_inventory(
                product=po_item.product,
                location=purchase_order.destination,
                quantity=qty_received,
                movement_type='purchase',
                reference_type='PurchaseOrderReceipt',
                reference_id=receipt.id,
                user=user,
                notes=f"Received from PO {purchase_order.po_number}"
            )
            
            # Update PO item received quantity
            po_item.received_quantity += qty_received
            po_item.save()  # This will auto-update status
            
            # Reduce incoming quantity
            inventory = InventoryLevel.objects.get(
                product=po_item.product,
                location=purchase_order.destination
            )
            inventory.quantity_incoming = max(0, inventory.quantity_incoming - qty_received)
            inventory.save()
    
    # Update PO status if all items received
    all_complete = all(item.status == 'complete' for item in purchase_order.items.all())
    if all_complete:
        purchase_order.status = 'received'
        purchase_order.actual_delivery_date = receipt.received_at.date()
    else:
        purchase_order.status = 'shipped'  # Partial receipt
    
    purchase_order.save()
    
    return receipt


@transaction.atomic
def cancel_purchase_order(purchase_order, reason='', user=None):
    """
    Cancel a purchase order.
    Removes incoming quantities if PO was confirmed.
    """
    if purchase_order.status in ['received', 'closed', 'cancelled']:
        raise ValidationError(f"Cannot cancel PO with status: {purchase_order.status}")
    
    # If confirmed, reduce incoming quantities
    if purchase_order.status in ['confirmed', 'shipped']:
        for item in purchase_order.items.all():
            remaining = item.ordered_quantity - item.received_quantity
            if remaining > 0:
                try:
                    inventory = InventoryLevel.objects.get(
                        product=item.product,
                        location=purchase_order.destination
                    )
                    inventory.quantity_incoming = max(0, inventory.quantity_incoming - remaining)
                    inventory.save()
                except InventoryLevel.DoesNotExist:
                    pass
    
    purchase_order.status = 'cancelled'
    purchase_order.notes = f"{purchase_order.notes}\n\nCancelled: {reason}" if reason else purchase_order.notes
    purchase_order.save()
    
    return purchase_order


# ============================================================================
# TRANSFER ORDER WORKFLOWS
# ============================================================================

@transaction.atomic
def approve_transfer_order(transfer_order, user=None):
    """
    Approve a transfer request.
    Validates that source location has sufficient stock.
    """
    if transfer_order.status != 'requested':
        raise ValidationError(f"Cannot approve transfer with status: {transfer_order.status}")
    
    # Validate stock availability
    for item in transfer_order.items.all():
        inventory = InventoryLevel.objects.get(
            product=item.product,
            location=transfer_order.from_location
        )
        
        available = inventory.quantity_available
        if available < item.requested_quantity:
            raise ValidationError(
                f"Insufficient stock for {item.product.name} at {transfer_order.from_location.name}. "
                f"Available: {available}, Requested: {item.requested_quantity}"
            )
    
    transfer_order.status = 'approved'
    transfer_order.approved_by = user
    transfer_order.save()
    
    return transfer_order


@transaction.atomic
def ship_transfer_order(transfer_order, user=None):
    """
    Ship a transfer order.
    Deducts from source location, marks as incoming at destination.
    """
    if transfer_order.status != 'approved':
        raise ValidationError(f"Cannot ship transfer with status: {transfer_order.status}")
    
    for item in transfer_order.items.all():
        # Deduct from source location
        update_inventory(
            product=item.product,
            location=transfer_order.from_location,
            quantity=-item.requested_quantity,  # Negative = deduction
            movement_type='transfer_out',
            reference_type='TransferOrder',
            reference_id=transfer_order.id,
            user=user,
            notes=f"Transfer to {transfer_order.to_location.name}"
        )
        
        # Mark as incoming at destination
        dest_inventory, _ = InventoryLevel.objects.get_or_create(
            product=item.product,
            location=transfer_order.to_location
        )
        dest_inventory.quantity_incoming += item.requested_quantity
        dest_inventory.save()
        
        # Update item
        item.shipped_quantity = item.requested_quantity
        item.status = 'shipped'
        item.save()
    
    # Update transfer status
    transfer_order.status = 'in_transit'
    transfer_order.shipped_at = timezone.now()
    transfer_order.save()
    
    return transfer_order


@transaction.atomic
def receive_transfer_order(transfer_order, user=None):
    """
    Receive a transfer order at destination.
    Adds to destination inventory.
    """
    if transfer_order.status != 'in_transit':
        raise ValidationError(f"Cannot receive transfer with status: {transfer_order.status}")
    
    for item in transfer_order.items.all():
        # Add to destination
        update_inventory(
            product=item.product,
            location=transfer_order.to_location,
            quantity=item.shipped_quantity,
            movement_type='transfer_in',
            reference_type='TransferOrder',
            reference_id=transfer_order.id,
            user=user,
            notes=f"Transfer from {transfer_order.from_location.name}"
        )
        
        # Reduce incoming quantity
        dest_inventory = InventoryLevel.objects.get(
            product=item.product,
            location=transfer_order.to_location
        )
        dest_inventory.quantity_incoming = max(0, dest_inventory.quantity_incoming - item.shipped_quantity)
        dest_inventory.save()
        
        # Update item
        item.received_quantity = item.shipped_quantity
        item.status = 'received'
        item.save()
    
    # Update transfer status
    transfer_order.status = 'completed'
    transfer_order.actual_arrival_date = timezone.now().date()
    transfer_order.save()
    
    return transfer_order


# ============================================================================
# SALES ORDER WORKFLOWS
# ============================================================================

@transaction.atomic
def fulfill_sales_order(sales_order, user=None):
    """
    Fulfill a sales order.
    Deducts inventory if available, creates backorders if not.
    
    Args:
        sales_order: SalesOrder instance
        user: User instance
    
    Returns:
        Dict with fulfillment details
    """
    if sales_order.status != 'pending':
        raise ValidationError(f"Cannot fulfill order with status: {sales_order.status}")
    
    fulfillment_result = {
        'fully_fulfilled': True,
        'items_fulfilled': [],
        'items_backordered': []
    }
    
    for item in sales_order.items.all():
        try:
            inventory = InventoryLevel.objects.select_for_update().get(
                product=item.product,
                location=sales_order.store
            )
        except InventoryLevel.DoesNotExist:
            # No inventory at all - full backorder
            backorder = BackOrder.objects.create(
                sales_order_item=item,
                product=item.product,
                location=sales_order.store,
                quantity_backordered=item.quantity_ordered
            )
            fulfillment_result['fully_fulfilled'] = False
            fulfillment_result['items_backordered'].append({
                'product': item.product.name,
                'quantity': item.quantity_ordered
            })
            continue
        
        available = inventory.quantity_available
        
        if available >= item.quantity_ordered:
            # Full fulfillment
            update_inventory(
                product=item.product,
                location=sales_order.store,
                quantity=-item.quantity_ordered,
                movement_type='sale',
                reference_type='SalesOrder',
                reference_id=sales_order.id,
                user=user,
                notes=f"Sale - Order {sales_order.order_number}"
            )
            
            item.quantity_fulfilled = item.quantity_ordered
            item.save()
            
            fulfillment_result['items_fulfilled'].append({
                'product': item.product.name,
                'quantity': item.quantity_ordered
            })
            
        elif available > 0:
            # Partial fulfillment
            update_inventory(
                product=item.product,
                location=sales_order.store,
                quantity=-available,
                movement_type='sale',
                reference_type='SalesOrder',
                reference_id=sales_order.id,
                user=user,
                notes=f"Partial sale - Order {sales_order.order_number}"
            )
            
            item.quantity_fulfilled = available
            item.save()
            
            # Create backorder for remainder
            backorder_qty = item.quantity_ordered - available
            backorder = BackOrder.objects.create(
                sales_order_item=item,
                product=item.product,
                location=sales_order.store,
                quantity_backordered=backorder_qty
            )
            
            fulfillment_result['fully_fulfilled'] = False
            fulfillment_result['items_fulfilled'].append({
                'product': item.product.name,
                'quantity': available
            })
            fulfillment_result['items_backordered'].append({
                'product': item.product.name,
                'quantity': backorder_qty
            })
        else:
            # No stock - full backorder
            backorder = BackOrder.objects.create(
                sales_order_item=item,
                product=item.product,
                location=sales_order.store,
                quantity_backordered=item.quantity_ordered
            )
            
            fulfillment_result['fully_fulfilled'] = False
            fulfillment_result['items_backordered'].append({
                'product': item.product.name,
                'quantity': item.quantity_ordered
            })
        
        # Record demand for reorder calculations
        DemandHistory.objects.update_or_create(
            product=item.product,
            location=sales_order.store,
            date=timezone.now().date(),
            defaults={
                'quantity_sold': models.F('quantity_sold') + item.quantity_ordered
            }
        )
    
    # Update order status
    if fulfillment_result['fully_fulfilled']:
        sales_order.status = 'fulfilled'
    elif fulfillment_result['items_fulfilled']:
        sales_order.status = 'partially_fulfilled'
    
    sales_order.fulfilled_at = timezone.now()
    sales_order.save()
    
    return fulfillment_result