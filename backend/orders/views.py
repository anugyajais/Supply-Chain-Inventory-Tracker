from django.db import transaction
from django.contrib import messages
from network.models import Location
from django.contrib.auth.decorators import login_required
from inventory.models import Product, InventoryLevel
from .models import PurchaseOrder, PurchaseOrderItem
from django.shortcuts import render, redirect, get_object_or_404

@login_required
def create_po(request):
    if request.method == 'POST':
        try:
            # Atomic transaction: if something fails, nothing saves
            with transaction.atomic():
                supplier_id = request.POST.get('supplier')
                destination_id = request.POST.get('destination')
                product_id = request.POST.get('product')
                quantity = int(request.POST.get('quantity'))
                unit_cost = float(request.POST.get('unit_cost'))

                supplier = Location.objects.get(id=supplier_id)
                destination = Location.objects.get(id=destination_id)
                product = Product.objects.get(id=product_id)

                # 1. Create the Purchase Order
                po = PurchaseOrder.objects.create(
                    supplier=supplier,
                    destination=destination,
                    status='draft',
                    created_by=request.user if request.user.is_authenticated else None 
                )

                # 2. Create the Line Item
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=product,
                    ordered_quantity=quantity,
                    unit_cost=unit_cost
                )
                
                # 3. Update total amount
                po.update_total()

                # Redirect to dashboard on success
                return redirect('dashboard')
                
        except Exception as e:
            context = get_dropdown_data()
            context['error'] = str(e)
            return render(request, 'order_create.html', context)

    # If it's a GET request, just load the empty form
    return render(request, 'order_create.html', get_dropdown_data())

def get_dropdown_data():
    """Helper to fetch active locations and products for the form dropdowns"""
    return {
        'suppliers': Location.objects.filter(location_type='supplier', is_active=True),
        'warehouses': Location.objects.filter(location_type__in=['warehouse', 'distribution'], is_active=True),
        'products': Product.objects.filter(is_active=True)
    }



@login_required
def order_list(request):
    # We added prefetch_related to safely and quickly grab the nested line items
    purchase_orders = PurchaseOrder.objects.select_related(
        'supplier', 'destination'
    ).prefetch_related(
        'items__product'  # <-- This is the magic addition!
    ).order_by('-created_at')
    
    return render(request, 'order_list.html', {'purchase_orders': purchase_orders})
@login_required
def receive_po(request, po_id):
    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        # Security check: Only receive it if it's not already received
        if po.status != 'received':
            try:
                # 1. Update the order status
                po.status = 'received'
                po.save()

                # 2. Loop through the items and update the physical inventory!
                for item in po.items.all():
                    # Get the inventory level at the destination warehouse, or create it if it's new
                    inventory, created = InventoryLevel.objects.get_or_create(
                        product=item.product,
                        location=po.destination,
                        defaults={'quantity_on_hand': 0, 'reorder_point': 10}
                    )
                    
                    # Add the received stock!
                    inventory.quantity_on_hand += item.ordered_quantity
                    inventory.save()
                
                messages.success(request, f"Success! PO #{po.id} received. Inventory has been updated.")
            except Exception as e:
                messages.error(request, f"Error processing receipt: {str(e)}")
        
    return redirect('order_list')