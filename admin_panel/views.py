from django.shortcuts import render, redirect, get_object_or_404
from auroramart.models import Product, Customer, Category, SubCategory
from .models import Transaction, TransactionItem, Inventory, InventoryItem, IncomingStock, InventoryHistory, Voucher
from ecommercemodule.models import Order, OrderItem
from .forms import ProductForm, CustomerForm
from .forms import ProductForm, CustomerForm, VoucherForm
from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField, Q, Sum, Count, F
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.admin.views.decorators import staff_member_required
from collections import defaultdict
from decimal import Decimal
import json

@staff_member_required(login_url='/admin_panel/login/')
def dashboard(request):
    # Get date range and granularity from query params (defaults: last 30 days, daily)
    from datetime import date as _date

    granularity = request.GET.get('granularity', 'daily')  # daily | monthly | yearly
    start_str = request.GET.get('start_date', '')
    end_str = request.GET.get('end_date', '')

    if start_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
        except Exception:
            start_date = timezone.now() - timedelta(days=30)
    else:
        start_date = timezone.now() - timedelta(days=30)

    if end_str:
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d')
        except Exception:
            end_date = timezone.now()
    else:
        end_date = timezone.now()

    # Normalize to date objects for period iteration
    start_dt = start_date.date() if hasattr(start_date, 'date') else start_date
    end_dt = end_date.date() if hasattr(end_date, 'date') else end_date

    # Fetch orders/transactions within the inclusive range
    orders = Order.objects.filter(created_at__date__gte=start_dt, created_at__date__lte=end_dt)
    transactions = Transaction.objects.filter(transaction_date__date__gte=start_dt, transaction_date__date__lte=end_dt)

    # Calculate KPIs (total amounts and counts across the selected range)
    order_total_amount = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    transaction_total_amount = transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    total_order_amount = order_total_amount + transaction_total_amount

    order_items_count = OrderItem.objects.filter(order__in=orders).count()
    transaction_items_count = TransactionItem.objects.filter(transaction__in=transactions).count()
    total_order_items = order_items_count + transaction_items_count

    order_units = OrderItem.objects.filter(order__in=orders).aggregate(total=Sum('quantity'))['total'] or 0
    transaction_units = TransactionItem.objects.filter(transaction__in=transactions).aggregate(total=Sum('quantity'))['total'] or 0
    total_order_units = order_units + transaction_units

    total_orders_count = orders.count() + transactions.count()

    # Build aggregated stats according to granularity
    daily_stats = []

    def month_iter(start_d, end_d):
        y, m = start_d.year, start_d.month
        while True:
            yield _date(y, m, 1)
            if y == end_d.year and m == end_d.month:
                break
            m += 1
            if m > 12:
                m = 1
                y += 1

    if granularity == 'monthly':
        for period_start in month_iter(start_dt, end_dt):
            y, m = period_start.year, period_start.month
            period_orders = orders.filter(created_at__year=y, created_at__month=m)
            period_transactions = transactions.filter(transaction_date__year=y, transaction_date__month=m)

            period_amount = (period_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')) + \
                            (period_transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0'))
            period_items = OrderItem.objects.filter(order__in=period_orders).count() + TransactionItem.objects.filter(transaction__in=period_transactions).count()
            period_units = (OrderItem.objects.filter(order__in=period_orders).aggregate(total=Sum('quantity'))['total'] or 0) + \
                           (TransactionItem.objects.filter(transaction__in=period_transactions).aggregate(total=Sum('quantity'))['total'] or 0)
            period_orders_count = period_orders.count() + period_transactions.count()

            daily_stats.append({
                'date': period_start.strftime('%Y-%m-%d'),
                'amount': float(period_amount),
                'items': period_items,
                'units': period_units,
                'orders': period_orders_count,
            })

    elif granularity == 'yearly':
        for yr in range(start_dt.year, end_dt.year + 1):
            period_orders = orders.filter(created_at__year=yr)
            period_transactions = transactions.filter(transaction_date__year=yr)

            period_amount = (period_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')) + \
                            (period_transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0'))
            period_items = OrderItem.objects.filter(order__in=period_orders).count() + TransactionItem.objects.filter(transaction__in=period_transactions).count()
            period_units = (OrderItem.objects.filter(order__in=period_orders).aggregate(total=Sum('quantity'))['total'] or 0) + \
                           (TransactionItem.objects.filter(transaction__in=period_transactions).aggregate(total=Sum('quantity'))['total'] or 0)
            period_orders_count = period_orders.count() + period_transactions.count()

            daily_stats.append({
                'date': _date(yr, 1, 1).strftime('%Y-%m-%d'),
                'amount': float(period_amount),
                'items': period_items,
                'units': period_units,
                'orders': period_orders_count,
            })

    else:
        # daily (default)
        current_date = start_dt
        while current_date <= end_dt:
            day_orders = orders.filter(created_at__date=current_date)
            day_transactions = transactions.filter(transaction_date__date=current_date)

            day_amount = (day_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')) + \
                         (day_transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0'))

            day_items = OrderItem.objects.filter(order__in=day_orders).count() + \
                        TransactionItem.objects.filter(transaction__in=day_transactions).count()

            day_units = (OrderItem.objects.filter(order__in=day_orders).aggregate(total=Sum('quantity'))['total'] or 0) + \
                        (TransactionItem.objects.filter(transaction__in=day_transactions).aggregate(total=Sum('quantity'))['total'] or 0)

            day_orders_count = day_orders.count() + day_transactions.count()

            daily_stats.append({
                'date': current_date.strftime('%Y-%m-%d'),  # Convert date to string for JSON serialization
                'amount': float(day_amount),
                'items': day_items,
                'units': day_units,
                'orders': day_orders_count,
            })

            current_date = current_date + timedelta(days=1)
    
    # === TOP SELLING PRODUCTS ===
    # Timeframe filter for the top products widget (all_time, last_year, last_month, last_week, today)
    top_timeframe = request.GET.get('top_timeframe', 'all_time')
    now = timezone.now()

    if top_timeframe == 'all_time':
        top_orders_qs = Order.objects.all()
        top_transactions_qs = Transaction.objects.all()
    elif top_timeframe == 'last_year':
        start_tf = now - timedelta(days=365)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif top_timeframe == 'last_month':
        start_tf = now - timedelta(days=30)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif top_timeframe == 'last_week':
        start_tf = now - timedelta(days=7)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif top_timeframe == 'today':
        today_date = now.date()
        top_orders_qs = Order.objects.filter(created_at__date=today_date)
        top_transactions_qs = Transaction.objects.filter(transaction_date__date=today_date)
    else:
        # fallback to all time
        top_orders_qs = Order.objects.all()
        top_transactions_qs = Transaction.objects.all()

    # Aggregate from both OrderItem and TransactionItem for the selected timeframe
    order_product_sales = OrderItem.objects.filter(order__in=top_orders_qs).values('product').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('unit_price'))
    )
    transaction_product_sales = TransactionItem.objects.filter(transaction__in=top_transactions_qs).values('product').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('price'))
    )

    # Combine product sales
    product_sales_dict = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0')})
    for item in order_product_sales:
        product_id = item['product']
        product_sales_dict[product_id]['qty'] += item['total_qty'] or 0
        product_sales_dict[product_id]['revenue'] += item['total_revenue'] or Decimal('0')

    for item in transaction_product_sales:
        product_id = item['product']
        product_sales_dict[product_id]['qty'] += item['total_qty'] or 0
        product_sales_dict[product_id]['revenue'] += item['total_revenue'] or Decimal('0')

    # Get top 5 products by quantity
    top_products_data = sorted(product_sales_dict.items(), key=lambda x: x[1]['qty'], reverse=True)[:5]
    top_products = []
    for product_id, data in top_products_data:
        try:
            product = Product.objects.get(pk=product_id)
            top_products.append({
                'name': product.name,
                'qty': data['qty'],
                'revenue': float(data['revenue']),
            })
        except Product.DoesNotExist:
            continue
    
    # === CATEGORY SALES ===
    # Get category breakdown
    category_sales = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0')})
    
    for item in OrderItem.objects.filter(order__in=orders).select_related('product__category'):
        if item.product.category:
            category_sales[item.product.category.name]['qty'] += item.quantity
            category_sales[item.product.category.name]['revenue'] += item.quantity * item.unit_price
    
    for item in TransactionItem.objects.filter(transaction__in=transactions).select_related('product__category'):
        if item.product.category:
            category_sales[item.product.category.name]['qty'] += item.quantity
            category_sales[item.product.category.name]['revenue'] += item.quantity * item.price
    
    category_chart_data = [{'name': k, 'qty': v['qty'], 'revenue': float(v['revenue'])} 
                           for k, v in sorted(category_sales.items(), key=lambda x: x[1]['revenue'], reverse=True)]
    
    # === EXISTING STATS (keep at bottom) ===
    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    inactive_products = Product.objects.filter(is_active=False).count()
    low_stock_products = Product.objects.filter(quantity_on_hand__lt=10).count()
    low_stock_items = Product.objects.filter(quantity_on_hand__lt=10).order_by('quantity_on_hand')[:5]
    recent_products = Product.objects.order_by('-id')[:5]
    top_rated = Product.objects.filter(rating__isnull=False).order_by('-rating')[:5]
    
    context = {
        # Sales analytics
        'total_order_amount': float(total_order_amount),
        'total_order_items': total_order_items,
        'total_order_units': total_order_units,
        'total_orders_count': total_orders_count,
        'daily_stats': daily_stats,
        'daily_stats_json': json.dumps(daily_stats),
        'top_products': top_products,
        'top_products_json': json.dumps(top_products),
    'top_timeframe': top_timeframe,
        'category_chart_data': category_chart_data,
        'category_chart_json': json.dumps(category_chart_data),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        
        # Existing stats
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
        'low_stock_products': low_stock_products,
        'low_stock_items': low_stock_items,
        'recent_products': recent_products,
        'top_rated': top_rated,
    }
    return render(request, 'admin_panel/dashboard.html', context)


def top_products_api(request):
    """Return top 5 products for a given timeframe as JSON.

    GET params:
      - timeframe: one of all_time, last_year, last_month, last_week, today
    """
    timeframe = request.GET.get('timeframe', 'all_time')
    now = timezone.now()

    if timeframe == 'all_time':
        top_orders_qs = Order.objects.all()
        top_transactions_qs = Transaction.objects.all()
    elif timeframe == 'last_year':
        start_tf = now - timedelta(days=365)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif timeframe == 'last_month':
        start_tf = now - timedelta(days=30)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif timeframe == 'last_week':
        start_tf = now - timedelta(days=7)
        top_orders_qs = Order.objects.filter(created_at__gte=start_tf)
        top_transactions_qs = Transaction.objects.filter(transaction_date__gte=start_tf)
    elif timeframe == 'today':
        today_date = now.date()
        top_orders_qs = Order.objects.filter(created_at__date=today_date)
        top_transactions_qs = Transaction.objects.filter(transaction_date__date=today_date)
    else:
        top_orders_qs = Order.objects.all()
        top_transactions_qs = Transaction.objects.all()

    order_product_sales = OrderItem.objects.filter(order__in=top_orders_qs).values('product').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('unit_price'))
    )
    transaction_product_sales = TransactionItem.objects.filter(transaction__in=top_transactions_qs).values('product').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('price'))
    )

    product_sales_dict = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0')})
    for item in order_product_sales:
        pid = item['product']
        product_sales_dict[pid]['qty'] += item['total_qty'] or 0
        product_sales_dict[pid]['revenue'] += item['total_revenue'] or Decimal('0')

    for item in transaction_product_sales:
        pid = item['product']
        product_sales_dict[pid]['qty'] += item['total_qty'] or 0
        product_sales_dict[pid]['revenue'] += item['total_revenue'] or Decimal('0')

    top_products_data = sorted(product_sales_dict.items(), key=lambda x: x[1]['qty'], reverse=True)[:5]
    top_products = []
    for pid, data in top_products_data:
        try:
            prod = Product.objects.get(pk=pid)
            top_products.append({'name': prod.name, 'qty': data['qty'], 'revenue': float(data['revenue'])})
        except Product.DoesNotExist:
            continue

    return JsonResponse({'top_products': top_products})


def admin_login(request):
    """Simple admin login view restricted to staff users."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.is_staff:
            auth_login(request, user)
            # honor "next" param if provided
            next_url = request.POST.get('next') or request.GET.get('next') or reverse('admin_panel:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid credentials or you are not authorized to access the admin panel.')

    # Render the login form (standalone full-page template)
    return render(request, 'admin_panel/admin_login_full.html', {})


def admin_logout(request):
    """Log out the current admin user and redirect to the admin login page."""
    auth_logout(request)
    return redirect('admin_panel:admin_login')

# Product
def product_list(request):
    from auroramart.models import SubCategory
    from urllib.parse import urlencode
    
    products = Product.objects.select_related('category', 'subcategory').all()

    # --- Filters ---
    category_filter = request.GET.get('category', '')
    subcategory_filter = request.GET.get('subcategory', '')
    active_filter = request.GET.get('active', '')
    search_query = request.GET.get('q', '')
    sku_query = request.GET.get('sku', '')
    price_order = request.GET.get('price_order', '')
    rating_order = request.GET.get('rating_order', '')
    stock_order = request.GET.get('stock_order', '')
    name_order = request.GET.get('name_order', '')
    category_order = request.GET.get('category_order', '')
    subcategory_order = request.GET.get('subcategory_order', '')
    status_order = request.GET.get('status_order', '')

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

    
    # --- Sorting ---
    # Priority: name > price > category > subcategory > stock > rating > status > default
    if name_order == 'asc':
        products = products.order_by('name')
    elif name_order == 'desc':
        products = products.order_by('-name')
    elif price_order == 'asc':
        products = products.order_by('unit_price')
    elif price_order == 'desc':
        products = products.order_by('-unit_price')
    elif category_order == 'asc':
        products = products.order_by('category__name', 'subcategory__name', 'name')
    elif category_order == 'desc':
        products = products.order_by('-category__name', '-subcategory__name', 'name')
    elif subcategory_order == 'asc':
        products = products.order_by('subcategory__name', 'name')
    elif subcategory_order == 'desc':
        products = products.order_by('-subcategory__name', 'name')
    elif stock_order == 'asc':
        products = products.order_by('quantity_on_hand')
    elif stock_order == 'desc':
        products = products.order_by('-quantity_on_hand')
    elif rating_order == 'asc':
        products = products.order_by('rating')
    elif rating_order == 'desc':
        products = products.order_by('-rating')
    elif status_order == 'asc':
        # Asc: show Active first
        products = products.order_by('-is_active', 'name')
    elif status_order == 'desc':
        # Desc: show Inactive first
        products = products.order_by('is_active', 'name')
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
    
    # Get subcategories with their parent category for dynamic filtering
    subcategories = SubCategory.objects.select_related('category').all().order_by('name')

    # --- Pagination ---
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- Build query params for pagination links (filters only, no sort params) ---
    query_params_dict = {}
    if category_filter:
        query_params_dict['category'] = category_filter
    if subcategory_filter:
        query_params_dict['subcategory'] = subcategory_filter
    if active_filter:
        query_params_dict['active'] = active_filter
    if search_query:
        query_params_dict['q'] = search_query
    if sku_query:
        query_params_dict['sku'] = sku_query
    
    query_params = urlencode(query_params_dict)
    
    # --- Build full query params including sort for current page (for edit/delete return URLs) ---
    full_query_params_dict = query_params_dict.copy()
    if price_order:
        full_query_params_dict['price_order'] = price_order
    if rating_order:
        full_query_params_dict['rating_order'] = rating_order
    if stock_order:
        full_query_params_dict['stock_order'] = stock_order
    if name_order:
        full_query_params_dict['name_order'] = name_order
    if category_order:
        full_query_params_dict['category_order'] = category_order
    if subcategory_order:
        full_query_params_dict['subcategory_order'] = subcategory_order
    if status_order:
        full_query_params_dict['status_order'] = status_order
    
    full_query_params = urlencode(full_query_params_dict)

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
        'name_order': name_order,
        'category_order': category_order,
        'subcategory_order': subcategory_order,
    'status_order': status_order,
        'query_params': query_params,  # Filter params only (for header sort links)
        'full_query_params': full_query_params,  # All params including sort (for edit/delete return URLs)
    }
    return render(request, 'admin_panel/product_list.html', context)


def voucher_list(request):
    """List vouchers in a table similar to product_list for quick UI preview."""
    from urllib.parse import urlencode

    vouchers = Voucher.objects.all()

    # --- Filters ---
    search_query = request.GET.get('q', '').strip()
    timeframe = request.GET.get('timeframe', '')  # expected values like '1','2','3','5','7','14','30','365'

    if search_query:
        vouchers = vouchers.filter(Q(name__icontains=search_query) | Q(code__icontains=search_query))

    if timeframe:
        # timeframe is treated as "up to X days" (inclusive). Special value 'gt30' means > 30 days.
        if timeframe == 'gt30':
            vouchers = vouchers.filter(days_valid__gt=30)
        else:
            try:
                days = int(timeframe)
                vouchers = vouchers.filter(days_valid__lte=days)
            except (ValueError, TypeError):
                pass

    # --- Ordering ---
    # allow simple ordering by name, days_valid, percent_off, cap_amount, created_at
    order = request.GET.get('order', '')
    if order == 'name_asc':
        vouchers = vouchers.order_by('name')
    elif order == 'name_desc':
        vouchers = vouchers.order_by('-name')
    elif order == 'days_asc':
        vouchers = vouchers.order_by('days_valid')
    elif order == 'days_desc':
        vouchers = vouchers.order_by('-days_valid')
    elif order == 'percent_asc':
        vouchers = vouchers.order_by('percent_off')
    elif order == 'percent_desc':
        vouchers = vouchers.order_by('-percent_off')
    elif order == 'cap_asc':
        vouchers = vouchers.order_by('cap_amount')
    elif order == 'cap_desc':
        vouchers = vouchers.order_by('-cap_amount')
    else:
        # Default natural ordering: ascending cap_amount (lowest max discount first), then ascending percent_off
        vouchers = vouchers.order_by('cap_amount', 'percent_off')

    # Pagination
    paginator = Paginator(vouchers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Query params for links
    query_params_dict = {}
    if search_query:
        query_params_dict['q'] = search_query
    if timeframe:
        query_params_dict['timeframe'] = timeframe
    if order:
        query_params_dict['order'] = order

    query_params = urlencode(query_params_dict)
    full_query_params = query_params

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'query_params': query_params,
        'full_query_params': full_query_params,
    }

    return render(request, 'admin_panel/voucher_list.html', context)

def product_add(request):
    # Capture the return URL from the referrer or default to product list
    return_url = request.GET.get('return_url', reverse('admin_panel:product_list'))
    
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" has been added successfully!')
            # Redirect back to the return URL
            return redirect(return_url)
        else:
            messages.error(request, 'There was an error adding the product. Please check the form.')
    else:
        form = ProductForm()
    
    return render(request, "admin_panel/product_form.html", {
        "form": form,
        "return_url": return_url,
    })


def voucher_add(request):
    """Create a new voucher (simple form for name, days_valid, percent_off, cap_amount)."""
    return_url = request.GET.get('return_url', reverse('admin_panel:voucher_list'))

    if request.method == 'POST':
        form = VoucherForm(request.POST)
        if form.is_valid():
            voucher = form.save()
            messages.success(request, f'Voucher "{voucher.name}" created successfully!')
            return redirect(return_url)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VoucherForm()

    return render(request, 'admin_panel/voucher_form.html', {
        'form': form,
        'return_url': return_url,
        'title': 'Add Voucher'
    })


def voucher_edit(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    return_url = request.GET.get('return_url', reverse('admin_panel:voucher_list'))

    if request.method == 'POST':
        form = VoucherForm(request.POST, instance=voucher)
        if form.is_valid():
            voucher = form.save()
            messages.success(request, f'Voucher "{voucher.name}" updated successfully!')
            return redirect(return_url)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VoucherForm(instance=voucher)

    return render(request, 'admin_panel/voucher_form.html', {
        'form': form,
        'return_url': return_url,
        'title': 'Edit Voucher'
    })


def voucher_delete(request, pk):
    voucher = get_object_or_404(Voucher, pk=pk)
    if request.method == 'POST':
        name = voucher.name
        voucher.delete()
        messages.success(request, f'Voucher "{name}" deleted successfully!')
        return redirect('admin_panel:voucher_list')
    return render(request, 'admin_panel/voucher_confirm_delete.html', {'voucher': voucher})

def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Capture the return URL from the referrer or default to product list
    return_url = request.GET.get('return_url', reverse('admin_panel:product_list'))
    
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" has been updated successfully!')
            # Redirect back to the return URL
            return redirect(return_url)
        else:
            messages.error(request, 'There was an error updating the product. Please check the form.')
    else:
        form = ProductForm(instance=product)
    
    return render(request, "admin_panel/product_form.html", {
        "form": form,
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

    # --- Build query params for pagination links ---
    from urllib.parse import urlencode
    query_params_dict = {}
    if search_id:
        query_params_dict['q'] = search_id
    if gender_filter:
        query_params_dict['gender'] = gender_filter
    if occupation_filter:
        query_params_dict['occupation'] = occupation_filter
    if education_filter:
        query_params_dict['education'] = education_filter
    if age_filter:
        query_params_dict['age'] = age_filter
    if age_order:
        query_params_dict['age_order'] = age_order
    if gender_order:
        query_params_dict['gender_order'] = gender_order
    if occupation_order:
        query_params_dict['occupation_order'] = occupation_order
    if education_order:
        query_params_dict['education_order'] = education_order
    
    query_params = urlencode(query_params_dict)

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
        'query_params': query_params,
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
def _customer_display(customer: Customer) -> str:
    """Prefer username; fall back to full name or Customer #id."""
    try:
        if customer and getattr(customer, 'user', None):
            user = customer.user
            if getattr(user, 'username', ''):
                return user.username
            full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
            if full_name:
                return full_name
    except Exception:
        pass
    # Fallback
    return f"Customer #{getattr(customer, 'pk', '')}"


def transaction_list(request):
    """Display unified customer purchases: ecommerce Orders + internal Transactions.
    Orders (from ecommercemodule) and Transactions (internal) are combined and sorted by date desc.
    """
    # Fetch ecommerce orders
    orders = Order.objects.select_related('customer').all()
    # Fetch internal transactions
    transactions = Transaction.objects.select_related('customer').all()

    # Normalize into a unified list of dicts
    unified = []
    for o in orders:
        unified.append({
            'source': 'order',
            'id': o.pk,
            'customer': o.customer,
            'customer_name': _customer_display(o.customer),
            'date': o.created_at,
            'total': o.total_amount,
            'status': getattr(o, 'status', ''),
        })
    for t in transactions:
        unified.append({
            'source': 'transaction',
            'id': t.transaction_id,
            'customer': t.customer,
            'customer_name': _customer_display(t.customer),
            'date': t.transaction_date,
            'total': t.total_amount,
            'status': '',
        })

    unified.sort(key=lambda r: r['date'], reverse=True)

    return render(request, 'admin_panel/transaction_list.html', {'records': unified})

# View items of a single transaction
def transaction_detail(request, pk):
    """Show detail for either an Order (ecommerce) or a Transaction (internal),
    with Bootstrap-friendly context and computed subtotals.
    """
    # Try order first
    order = Order.objects.select_related('customer__user').filter(pk=pk).first()
    if order:
        items_qs = order.items.select_related('product').all()
        items = [
            {
                'product': it.product,
                'quantity': it.quantity,
                'price': it.unit_price,
                'subtotal': it.unit_price * it.quantity,
            }
            for it in items_qs
        ]
        return render(request, 'admin_panel/transaction_detail.html', {
            'order': order,
            'items': items,
            'is_order': True,
            'customer_username': _customer_display(order.customer),
        })
    # Fallback to internal transaction
    transaction = get_object_or_404(Transaction.objects.select_related('customer__user'), pk=pk)
    items_qs = transaction.items.select_related('product').all()
    items = [
        {
            'product': it.product,
            'quantity': it.quantity,
            'price': it.price,
            'subtotal': it.price * it.quantity,
        }
        for it in items_qs
    ]
    return render(request, 'admin_panel/transaction_detail.html', {
        'transaction': transaction,
        'items': items,
        'is_order': False,
        'customer_username': _customer_display(transaction.customer),
    })
    
def inventory_list(request):
    products = Product.objects.all()

    # --- Search / Filters ---
    search_query = request.GET.get('q', '')
    sku_query = request.GET.get('sku', '')
    below_reorder = request.GET.get('below_reorder', '')

    if search_query:
        products = products.filter(name__icontains=search_query)
    if sku_query:
        exact_match = products.filter(sku__iexact=sku_query)
        if exact_match.exists():
            products = exact_match
        else:
            products = products.filter(sku__icontains=sku_query)

    # --- Low stock filter: products at or below their reorder quantity ---
    if below_reorder:
        products = products.filter(quantity_on_hand__lte=F('reorder_quantity'))

    # --- Auto-place orders for low stock items: set order_cart to reorder_quantity when filter active ---
    # This runs on GET (not POST) so it won't interfere with manual cart updates submitted via the form.
    if below_reorder and request.method != 'POST':
        try:
            order_cart = request.session.get('order_cart', {})
        except Exception:
            order_cart = {}

        # Set the order quantity for each product in the filtered queryset to its reorder_quantity
        # but only if the product is not already present in the session cart. This prevents
        # overwriting manual edits or button clicks which update the session on POST.
        for p in products:
            pid = str(p.id)
            if pid in order_cart:
                # preserve any existing user-set quantity
                continue
            try:
                order_cart[pid] = int(p.reorder_quantity or 0)
            except Exception:
                # If reorder_quantity isn't an int or missing, skip
                continue

        request.session['order_cart'] = order_cart

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
        'below_reorder': below_reorder,
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


def get_subcategories(request, category_id):
    """
    API endpoint to get subcategories for a given category.
    Returns JSON response with subcategory data.
    """
    try:
        category = get_object_or_404(Category, pk=category_id)
        subcategories = SubCategory.objects.filter(category=category).order_by('name')
        
        data = {
            'subcategories': [
                {
                    'id': sub.id,
                    'name': sub.name,
                    'display_name': str(sub)
                }
                for sub in subcategories
            ]
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def order_update_status(request, pk):
    """Update an ecommerce order's status from the transactions page."""
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in Order.StatusChoices.choices]
        if new_status in valid_statuses:
            previous_status = order.status
            order.status = new_status
            order.save()

            # If the order was cancelled now (and wasn't cancelled before), restore inventory quantities
            if new_status == Order.StatusChoices.CANCELLED and previous_status != Order.StatusChoices.CANCELLED:
                for item in order.items.select_related('product').all():
                    prod = item.product
                    # add back the cancelled quantity
                    prod.quantity_on_hand = (prod.quantity_on_hand or 0) + (item.quantity or 0)
                    prod.save()

                    # Create an incoming InventoryHistory entry to reflect the restock, but avoid duplicates
                    if not InventoryHistory.objects.filter(product=prod, movement_type='incoming', reference_id=order.pk).exists():
                        note = f"Restored from order #{order.pk}"
                        InventoryHistory.objects.create(
                            product=prod,
                            movement_type='incoming',
                            quantity=item.quantity,
                            reference_id=order.pk,
                            notes=note + " (Cancelled)",
                        )

                    # Find any outgoing inventory history linked to this order and append (Cancelled) to its notes
                    outgoing_qs = InventoryHistory.objects.filter(
                        product=prod, movement_type='outgoing', reference_id=order.pk
                    )
                    for rec in outgoing_qs:
                        existing = rec.notes or ''
                        if '(Cancelled)' not in existing:
                            rec.notes = (existing + ' ' + '(Cancelled)').strip()
                            rec.save()

            messages.success(request, f"Order #{order.pk} status updated to {new_status}.")
        else:
            messages.error(request, "Invalid status selected.")
    return redirect('admin_panel:transaction_list')

