from django.shortcuts import render, redirect, get_object_or_404
from auroramart.models import Product, Customer
from .models import Transaction, Inventory, InventoryItem, IncomingStock, InventoryHistory
from .forms import ProductForm, CustomerForm
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField, Q, Sum
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from datetime import datetime

def dashboard(request):
    # Get statistics
    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    inactive_products = Product.objects.filter(is_active=False).count()
    low_stock_products = Product.objects.filter(quantity_on_hand__lt=10).count()
    
    # Get low stock items (for alerts)
    low_stock_items = Product.objects.filter(quantity_on_hand__lt=10).order_by('quantity_on_hand')[:5]
    
    # Get recently added products
    recent_products = Product.objects.order_by('-id')[:5]
    
    # Get top rated products
    top_rated = Product.objects.filter(rating__isnull=False).order_by('-rating')[:5]
    
    context = {
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
        'low_stock_products': low_stock_products,
        'low_stock_items': low_stock_items,
        'recent_products': recent_products,
        'top_rated': top_rated,
    }
    return render(request, 'admin_panel/dashboard.html', context)

# Product
def product_list(request):
    products = Product.objects.all()

    # --- Filters ---
    category_filter = request.GET.get('category', '')
    subcategory_filter = request.GET.get('subcategory', '')
    active_filter = request.GET.get('active', '')
    search_query = request.GET.get('q', '')
    sku_query = request.GET.get('sku', '')
    price_order = request.GET.get('price_order', '')
    rating_order = request.GET.get('rating_order', '')
    stock_order = request.GET.get('stock_order', '')

    if category_filter:
        products = products.filter(category__name=category_filter)
    if subcategory_filter:
        products = products.filter(subcategory__name=subcategory_filter)
    if active_filter:
        if active_filter.lower() == 'active':
            products = products.filter(is_active=True)
        elif active_filter.lower() == 'inactive':
            products = products.filter(is_active=False)
    if search_query:
        products = products.filter(name__icontains=search_query)
    if sku_query:
        # First try exact match
        exact_match = products.filter(sku__iexact=sku_query)
        if exact_match.exists():
            products = exact_match
        else:
            # If no exact match, show partial matches
            products = products.filter(sku__icontains=sku_query)
    
    # --- Sorting (priority: price > rating > stock > default) ---
    if price_order == 'asc':
        products = products.order_by('unit_price')
    elif price_order == 'desc':
        products = products.order_by('-unit_price')
    elif rating_order == 'asc':
        products = products.order_by('rating')
    elif rating_order == 'desc':
        products = products.order_by('-rating')
    elif stock_order == 'asc':
        products = products.order_by('quantity_on_hand')
    elif stock_order == 'desc':
        products = products.order_by('-quantity_on_hand')
    else:
        # Default: sort alphabetically by name, or by SKU if searching SKU
        if sku_query:
            products = products.order_by('sku')
        else:
            products = products.order_by('name')

    # --- Distinct values for dropdowns ---
    categories = (
        Product.objects.values_list('category__name', flat=True)
        .distinct()
        .order_by('category__name')
    )
    subcategories = (
        Product.objects.values_list('subcategory__name', flat=True)
        .distinct()
        .order_by('subcategory__name')
    )

    # --- Pagination ---
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'subcategories': subcategories,
        'category_filter': category_filter,
        'subcategory_filter': subcategory_filter,
        'active_filter': active_filter,
        'search_query': search_query,
        'sku_query': sku_query,
        'price_order': price_order,
        'rating_order': rating_order,
        'stock_order': stock_order,
    }
    return render(request, 'admin_panel/product_list.html', context)

def product_add(request):
    # Capture the return URL from the referrer or default to product list
    return_url = request.GET.get('return_url', reverse('admin_panel:product_list'))
    
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" has been added successfully!')
            # Redirect back to the return URL
            return redirect(return_url)
        else:
            messages.error(request, 'There was an error adding the product. Please check the form.')
    else:
        form = ProductForm()
    
    # Get existing categories and subcategories for datalist
    categories = (
        Product.objects.values_list('category__name', flat=True)
        .distinct()
        .order_by('category__name')
    )
    subcategories = (
        Product.objects.values_list('subcategory__name', flat=True)
        .distinct()
        .order_by('subcategory__name')
    )
    
    return render(request, "admin_panel/product_form.html", {
        "form": form,
        "categories": categories,
        "subcategories": subcategories,
        "return_url": return_url,
    })

def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Capture the return URL from the referrer or default to product list
    return_url = request.GET.get('return_url', reverse('admin_panel:product_list'))
    
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" has been updated successfully!')
            # Redirect back to the return URL
            return redirect(return_url)
        else:
            messages.error(request, 'There was an error updating the product. Please check the form.')
    else:
        form = ProductForm(instance=product)
    
    # Get existing categories and subcategories for datalist
    categories = (
        Product.objects.values_list('category__name', flat=True)
        .distinct()
        .order_by('category__name')
    )
    subcategories = (
        Product.objects.values_list('subcategory__name', flat=True)
        .distinct()
        .order_by('subcategory__name')
    )
    
    return render(request, "admin_panel/product_form.html", {
        "form": form,
        "categories": categories,
        "subcategories": subcategories,
        "return_url": return_url,
    })

def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product_name = product.name  # Store name before deletion
    
    if request.method == "POST":
        product.delete()
        messages.success(request, f'Product "{product_name}" has been deleted successfully!')
        return redirect("admin_panel:product_list")
    
    return render(request, "admin_panel/product_confirm_delete.html", {"product": product})



def customer_list(request):
    customers = Customer.objects.all()

    # --- Filters ---
    search_id = request.GET.get('q', '').strip()
    gender_filter = request.GET.get('gender', '')
    occupation_filter = request.GET.get('occupation', '')
    education_filter = request.GET.get('education', '')
    age_filter = request.GET.get('age', '')

    if search_id:
        customers = customers.filter(id__icontains=search_id)
    if gender_filter:
        customers = customers.filter(gender=gender_filter)
    if occupation_filter:
        customers = customers.filter(occupation=occupation_filter)
    if education_filter:
        customers = customers.filter(education=education_filter)
    if age_filter:
        try:
            age_value = int(age_filter)
            customers = customers.filter(age__lte=age_value)
        except ValueError:
            pass

    # --- Sorting (Priority: age > gender > occupation > education) ---
    age_order = request.GET.get('age_order', '')
    gender_order = request.GET.get('gender_order', '')
    occupation_order = request.GET.get('occupation_order', '')
    education_order = request.GET.get('education_order', '')

    # Education hierarchy
    education_hierarchy = ["Secondary", "Diploma", "Bach Degree", "Masters"]
    
    # Gender order: Male, Female
    gender_hierarchy = ["Male", "Female"]

    if age_order == 'asc':
        customers = customers.order_by('age')
    elif age_order == 'desc':
        customers = customers.order_by('-age')
    elif gender_order == 'asc':
        # Male first, then Female
        when_cases = [When(gender=g, then=Value(pos)) for pos, g in enumerate(gender_hierarchy)]
        customers = customers.annotate(
            gender_rank=Case(*when_cases, default=Value(999), output_field=IntegerField())
        ).order_by('gender_rank')
    elif gender_order == 'desc':
        # Female first, then Male
        when_cases = [When(gender=g, then=Value(pos)) for pos, g in enumerate(reversed(gender_hierarchy))]
        customers = customers.annotate(
            gender_rank=Case(*when_cases, default=Value(999), output_field=IntegerField())
        ).order_by('gender_rank')
    elif occupation_order == 'asc':
        customers = customers.order_by('occupation')
    elif occupation_order == 'desc':
        customers = customers.order_by('-occupation')
    elif education_order == 'asc':
        # Secondary to Masters
        when_cases = [When(education=level, then=Value(pos)) for pos, level in enumerate(education_hierarchy)]
        customers = customers.annotate(
            edu_rank=Case(*when_cases, default=Value(999), output_field=IntegerField())
        ).order_by('edu_rank')
    elif education_order == 'desc':
        # Masters to Secondary
        when_cases = [When(education=level, then=Value(len(education_hierarchy) - pos)) for pos, level in enumerate(education_hierarchy)]
        customers = customers.annotate(
            edu_rank=Case(*when_cases, default=Value(0), output_field=IntegerField())
        ).order_by('-edu_rank')
    else:
        # Default sorting by ID
        customers = customers.order_by('id')

    # --- Pagination ---
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- Distinct values for dropdowns ---
    genders = Customer.objects.values_list('gender', flat=True).distinct().order_by('gender')
    occupations = Customer.objects.values_list('occupation', flat=True).distinct().order_by('occupation')
    educations = education_hierarchy  # Use the hierarchy order

    context = {
        'page_obj': page_obj,
        'search_id': search_id,
        'gender_filter': gender_filter,
        'occupation_filter': occupation_filter,
        'education_filter': education_filter,
        'age_filter': age_filter,
        'age_order': age_order,
        'gender_order': gender_order,
        'occupation_order': occupation_order,
        'education_order': education_order,
        'genders': genders,
        'occupations': occupations,
        'educations': educations,
    }

    return render(request, 'admin_panel/customer_list.html', context)


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return_url = request.GET.get('return_url', reverse('admin_panel:customer_list'))
    return render(request, 'admin_panel/customer_detail.html', {'customer': customer, 'return_url': return_url})

def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    
    # Capture the return URL from the referrer or default to customer list
    return_url = request.GET.get('return_url', reverse('admin_panel:customer_list'))
    
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.id}" has been updated successfully!')
            # Redirect back to the return URL
            return redirect(return_url)
        else:
            messages.error(request, 'There was an error updating the customer. Please check the form.')
    else:
        form = CustomerForm(instance=customer)
    
    # Get existing values for datalists
    genders = Customer.objects.values_list('gender', flat=True).distinct().order_by('gender')
    occupations = Customer.objects.values_list('occupation', flat=True).distinct().order_by('occupation')
    educations = ["Secondary", "Diploma", "Bach Degree", "Masters"]
    
    return render(request, "admin_panel/customer_form.html", {
        "form": form,
        "customer": customer,
        "genders": genders,
        "occupations": occupations,
        "educations": educations,
        "return_url": return_url,
    })

# List all transactions
def transaction_list(request):
    transactions = Transaction.objects.all().order_by('-transaction_date')
    return render(request, 'admin_panel/transaction_list.html', {'transactions': transactions})

# View items of a single transaction
def transaction_detail(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    items = transaction.items.all()  # Related TransactionItem objects
    return render(request, 'admin_panel/transaction_detail.html', {
        'transaction': transaction,
        'items': items
    })
    
def inventory_list(request):
    products = Product.objects.all()

    # --- Search / Filters ---
    search_query = request.GET.get('q', '')
    sku_query = request.GET.get('sku', '')

    if search_query:
        products = products.filter(name__icontains=search_query)
    if sku_query:
        exact_match = products.filter(sku__iexact=sku_query)
        if exact_match.exists():
            products = exact_match
        else:
            products = products.filter(sku__icontains=sku_query)

    # --- Handle POST: update order quantity ---
    if request.method == 'POST':
        order_cart = request.session.get('order_cart', {})

        # PRIORITY 1: Check if a button (increment/decrement) was clicked
        increment_id = request.POST.get('increment')
        decrement_id = request.POST.get('decrement')

        if increment_id:
            # Increment button clicked
            pid = str(increment_id)
            current_qty = order_cart.get(pid, 0)
            order_cart[pid] = current_qty + 1
        elif decrement_id:
            # Decrement button clicked
            pid = str(decrement_id)
            current_qty = order_cart.get(pid, 0)
            if current_qty > 1:
                order_cart[pid] = current_qty - 1
            else:
                # Remove from cart if quantity would be 0 or negative
                if pid in order_cart:
                    del order_cart[pid]
        else:
            # PRIORITY 2: No buttons clicked, check for manual input (Enter key in input field)
            # Process all order_qty_* fields and update cart
            for key, value in request.POST.items():
                if key.startswith('order_qty_'):
                    pid = key.replace('order_qty_', '')
                    try:
                        qty = int(value) if value and value.strip() else 0
                        if qty > 0:
                            order_cart[pid] = qty
                        elif pid in order_cart:
                            del order_cart[pid]
                    except (ValueError, TypeError):
                        continue

        request.session['order_cart'] = order_cart
        return redirect(request.path)  # refresh page

    # --- Pagination ---
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # --- Attach order_qty and incoming_stock from session for each product ---
    order_cart = request.session.get('order_cart', {})
    
    for product in page_obj:
        product.order_qty = order_cart.get(str(product.id), 0)
        
        # Calculate incoming stock (all confirmed + received shipments for this product)
        try:
            incoming_qty = IncomingStock.objects.filter(
                product_id=product.id,
                status__in=['confirmed', 'received']
            ).values_list('quantity', flat=True)
            product.incoming_stock_qty = sum(incoming_qty) if incoming_qty else 0
        except Exception as e:
            product.incoming_stock_qty = 0

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'sku_query': sku_query,
    }
    return render(request, 'admin_panel/inventory_list.html', context)

def order_list(request):
    order_cart = request.session.get('order_cart', {})
    
    # Handle checkout action
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'checkout':
            checked_products = request.POST.getlist('checkout_products')
            
            if checked_products:
                # Store checked items in a temporary checkout session
                checkout_items = {}
                for product_id in checked_products:
                    if product_id in order_cart:
                        checkout_items[product_id] = order_cart[product_id]
                
                request.session['checkout_items'] = checkout_items
                return redirect('admin_panel:checkout_form')
            else:
                messages.warning(request, 'Please select at least one item to checkout.')
    
    products = []

    for product_id, qty in order_cart.items():
        try:
            product = Product.objects.get(pk=product_id)
            product.ordered_qty = qty
            products.append(product)
        except Product.DoesNotExist:
            continue

    context = {
        'products': products,
    }
    return render(request, 'admin_panel/order_list.html', context)


def checkout_form(request):
    checkout_items = request.session.get('checkout_items', {})
    
    if not checkout_items:
        messages.warning(request, 'No items to checkout.')
        return redirect('admin_panel:order_list')
    
    # Prepare checkout data with product details
    checkout_products = []
    for product_id, qty in checkout_items.items():
        try:
            product = Product.objects.get(pk=product_id)
            checkout_products.append({
                'product_id': product_id,
                'name': product.name,
                'sku': product.sku,
                'quantity': qty,
                'unit_price': product.unit_price,
                'total_price': float(product.unit_price) * qty,
            })
        except Product.DoesNotExist:
            continue
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm_shipment':
            # Create IncomingStock records and remove from order_cart
            order_cart = request.session.get('order_cart', {})
            for product_id, qty in checkout_items.items():
                try:
                    product = Product.objects.get(pk=product_id)
                    # Create incoming stock record
                    IncomingStock.objects.create(
                        product=product,
                        quantity=qty,
                        status='confirmed',
                        confirmation_date=timezone.now()
                    )
                    # Update reorder_quantity to reflect shipped amount
                    product.reorder_quantity = qty
                    product.save()
                    
                    # Remove from order cart
                    if product_id in order_cart:
                        del order_cart[product_id]
                except Product.DoesNotExist:
                    continue
            
            request.session['order_cart'] = order_cart
            request.session.pop('checkout_items', None)
            messages.success(request, f'Shipment confirmed! {len(checkout_items)} item(s) added to Incoming Stock.')
            return redirect('admin_panel:incoming_stock')
        elif action == 'cancel':
            request.session.pop('checkout_items', None)
            return redirect('admin_panel:order_list')
    
    total_amount = sum(item['total_price'] for item in checkout_products)
    
    context = {
        'checkout_products': checkout_products,
        'total_amount': total_amount,
    }
    return render(request, 'admin_panel/checkout_form.html', context)


def incoming_stock(request):
    # Handle marking shipments as received/unreceived
    if request.method == 'POST':
        # Check if this is a "Move to History" action
        move_to_history = request.POST.get('action') == 'move_to_history'
        shipments_to_move = request.POST.getlist('move_to_history_shipments')
        
        if move_to_history and shipments_to_move:
            # Move selected arrived shipments to history and update stock
            moved_count = 0
            for shipment_id in shipments_to_move:
                try:
                    shipment = IncomingStock.objects.get(shipment_id=shipment_id, status='received')
                    
                    # Create history record
                    InventoryHistory.objects.create(
                        product=shipment.product,
                        movement_type='incoming',
                        quantity=shipment.quantity,
                        reference_id=shipment.shipment_id,
                        notes=f'Shipment {shipment.shipment_id} received on {shipment.received_date}'
                    )
                    
                    # INCREASE quantity_on_hand by the incoming stock quantity
                    product = shipment.product
                    product.quantity_on_hand += shipment.quantity
                    product.save()
                    
                    # Archive the shipment
                    shipment.archived = True
                    shipment.save()
                    moved_count += 1
                except IncomingStock.DoesNotExist:
                    continue
            
            messages.success(request, f'{moved_count} shipment(s) moved to inventory history and stock updated!')
            return redirect(request.path)
        else:
            # Original logic: mark as received/unreceived via checkboxes
            received_shipments = request.POST.getlist('received_shipments')
            
            # Get all shipments
            all_shipments = IncomingStock.objects.filter(status__in=['confirmed', 'received'], archived=False)
            
            # Track changes
            marked_arrived = 0
            marked_unconfirmed = 0
            
            # Process all shipments to check if they were checked or unchecked
            for shipment in all_shipments:
                shipment_id_str = str(shipment.shipment_id)
                
                if shipment_id_str in received_shipments:
                    # Checkbox is checked - mark as received if not already
                    if shipment.status != 'received':
                        shipment.status = 'received'
                        shipment.received_date = timezone.now()
                        shipment.save()
                        # NOTE: Don't update quantity_on_hand here - it will be updated when moved to history
                        marked_arrived += 1
                else:
                    # Checkbox is unchecked - mark as confirmed if was received
                    if shipment.status == 'received':
                        shipment.status = 'confirmed'
                        shipment.received_date = None
                        shipment.save()
                        marked_unconfirmed += 1

                        marked_unconfirmed += 1
            
            # Show appropriate message
            total_changes = marked_arrived + marked_unconfirmed
            if total_changes > 0:
                message = f'{marked_arrived} shipment(s) marked as Arrived' if marked_arrived > 0 else ''
                if marked_unconfirmed > 0:
                    message += (', ' if message else '') + f'{marked_unconfirmed} shipment(s) reverted to Confirmed'
                messages.success(request, message + '!')
                return redirect(request.path)
            else:
                messages.info(request, 'No changes made.')
    
    # Get all incoming stock items (excluding archived)
    incoming = IncomingStock.objects.filter(archived=False).order_by('-order_date')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        incoming = incoming.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(incoming, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'admin_panel/incoming_stock.html', context)


def inventory_history(request):
    """
    Display inventory movement history showing incoming and outgoing stock movements.
    """
    # Get all inventory history records
    history = InventoryHistory.objects.all().order_by('-movement_date')
    
    # Filter by movement type
    movement_filter = request.GET.get('movement_type', '')
    if movement_filter:
        history = history.filter(movement_type=movement_filter)
    
    # Search by product name or SKU
    search_query = request.GET.get('search', '')
    if search_query:
        history = history.filter(
            product__name__icontains=search_query
        ) | history.filter(
            product__sku__icontains=search_query
        )
    
    # Pagination
    paginator = Paginator(history, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'movement_filter': movement_filter,
        'search_query': search_query,
    }
    return render(request, 'admin_panel/inventory_history.html', context)

