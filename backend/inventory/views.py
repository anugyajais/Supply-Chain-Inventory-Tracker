from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import F, Sum
from .models import InventoryLevel
from network.models import Location
from orders.models import PurchaseOrder
from django.contrib.auth.decorators import login_required
from .forms import ProductForm


@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            new_product = form.save()
            messages.success(request, f"Product '{new_product.name}' added to catalog successfully!")
            return redirect('inventory_list') # Send them to inventory to see it
    else:
        form = ProductForm()
    
    return render(request, 'product_create.html', {'form': form})

@login_required
def dashboard(request):
    # Fetch all inventory items
    inventory_items = InventoryLevel.objects.select_related('product', 'location')
    
    # 1. Calculate Total Inventory Value
    total_value = inventory_items.annotate(
        value=F('quantity_on_hand') * F('product__unit_cost')
    ).aggregate(total=Sum('value'))['total'] or 0

    # 2. Count Low Stock Items
    low_stock_count = inventory_items.filter(
        quantity_on_hand__lt=F('reorder_point'),
        reorder_point__gt=0
    ).count()

    # 3. Count Active Purchase Orders (not received/closed/cancelled)
    active_orders = PurchaseOrder.objects.exclude(
        status__in=['received', 'closed', 'cancelled']
    ).count()

    # 4. Total Locations
    locations_count = Location.objects.count()

    # 5. Get top 5 low stock items to display in a table
    low_stock_items = inventory_items.filter(
        quantity_on_hand__lt=F('reorder_point'),
        reorder_point__gt=0
    ).order_by('quantity_on_hand')[:5]

    context = {
        'total_value': total_value,
        'low_stock_count': low_stock_count,
        'active_orders': active_orders,
        'locations_count': locations_count,
        'low_stock_items': low_stock_items,
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def inventory_list(request):
    # Fetch all inventory levels, joined with Product and Location data for speed
    inventory_items = InventoryLevel.objects.select_related('product', 'location').all()

    context = {
        'inventory_items': inventory_items,
    }
    return render(request, 'inventory_list.html', context)


# This acts as a bouncer: Only returns True if the user is an admin
def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin, login_url='/') # Kicks non-admins back to dashboard
def add_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            messages.success(request, f"Account created for {new_user.username}!")
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'add_user.html', {'form': form})

@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            new_product = form.save()
            messages.success(request, f"Product '{new_product.name}' added to catalog successfully!")
            return redirect('inventory_list') # Send them to inventory to see it
    else:
        form = ProductForm()
    
    return render(request, 'product_create.html', {'form': form})

