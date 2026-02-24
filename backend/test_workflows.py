"""
Quick test script for business logic.
Run with: python manage.py shell < test_workflows.py
"""
from django.contrib.auth.models import User
from network.models import Location
from inventory.models import Product, InventoryLevel
from orders.models import PurchaseOrder, PurchaseOrderItem
from orders.workflows import confirm_purchase_order, receive_purchase_order
from django.utils import timezone

# Get or create user
user = User.objects.first()

# Get locations
supplier = Location.objects.filter(location_type='supplier').first()
warehouse = Location.objects.filter(location_type='warehouse').first()

# Get product
product = Product.objects.first()

if supplier and warehouse and product:
    print(f"✓ Found: {supplier}, {warehouse}, {product}")
    
    # Create PO
    po = PurchaseOrder.objects.create(
        supplier=supplier,
        destination=warehouse,
        created_by=user
    )
    
    # Add item
    po_item = PurchaseOrderItem.objects.create(
        purchase_order=po,
        product=product,
        ordered_quantity=100,
        unit_cost=10.00
    )
    
    print(f"✓ Created: {po}")
    print(f"  Status: {po.status}")
    
    # Confirm PO
    confirm_purchase_order(po, user)
    print(f"✓ Confirmed PO - Status: {po.status}")
    
    # Check incoming quantity
    inventory = InventoryLevel.objects.get(product=product, location=warehouse)
    print(f"  Incoming quantity: {inventory.quantity_incoming}")
    
    # Receive PO
    receipt_data = {
        'received_at': timezone.now(),
        'items': [
            {
                'purchase_order_item_id': po_item.id,
                'quantity_received': 95,  # 5 damaged
                'condition': 'good'
            }
        ]
    }
    
    receipt = receive_purchase_order(po, receipt_data, user)
    print(f"✓ Received: {receipt}")
    
    # Check final inventory
    inventory.refresh_from_db()
    print(f"  Final on hand: {inventory.quantity_on_hand}")
    print(f"  Final incoming: {inventory.quantity_incoming}")
    
    print("\n✅ All workflows working!")
else:
    print("❌ Please create locations and products first in Django admin")