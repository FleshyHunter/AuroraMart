from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordChangeView

from .forms import StorePasswordResetForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Avg, Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    AddToCartForm,
    CartItemUpdateForm,
    CheckoutConfirmForm,
    CheckoutForm,
    CustomerForm,
    CustomerAddressForm,
    LoginForm,
    RegistrationForm,
    ReviewForm,
    StorePasswordResetForm,
)
from auroramart.models import Category, Customer, Product, SubCategory
from .models import Cart, CartItem, CustomerAddress, Order, OrderItem, Review
from auroramart.ml import (
    predict_customer_preferred_category as ml_predict_preferred_category,
    frequently_bought_together as ml_fbt,
    cart_add_on_recommendations as ml_cart_recs,
    category_exploration_recommendations as ml_category_explore,
)


def _get_or_create_profile(user):
    profile, _ = Customer.objects.get_or_create(user=user)
    return profile


def _ensure_cart(request):
    if request.user.is_authenticated:
        profile = _get_or_create_profile(request.user)
        cart, _ = Cart.objects.get_or_create(customer=profile, defaults={"session_key": None})
        return cart
    if not request.session.session_key:
        request.session.create()
    cart, _ = Cart.objects.get_or_create(
        session_key=request.session.session_key, defaults={"customer": None}
    )
    return cart


def _cart_overview(cart):
    items = list(cart.items.select_related("product"))
    cart_total = sum(
        (item.product.unit_price * item.quantity for item in items),
        Decimal("0.00"),
    )
    item_count = sum(item.quantity for item in items)
    return cart_total, item_count, items


def _safe_redirect(request, fallback):
    redirect_to = request.POST.get("redirect_to") or request.GET.get("next") or request.META.get(
        "HTTP_REFERER"
    )
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to, allowed_hosts={request.get_host()}
    ):
        return redirect_to
    return fallback


def home(request):
    categories = Category.objects.prefetch_related("subcategories").all()
    featured_products = Product.objects.filter(is_active=True).order_by("-rating", "name")[:8]
    fast_selling_products = (
        Product.objects.filter(is_active=True, quantity_on_hand__gt=0, quantity_on_hand__lt=10)
        .order_by("quantity_on_hand", "-rating")[:8]
    )
    preferred_products = None
    preferred_category = None
    if request.user.is_authenticated:
        profile = _get_or_create_profile(request.user)
        preferred_category = profile.preferred_category
        # Cold-start: if user has no saved preference, attempt ML prediction (best effort)
        if not preferred_category:
            predicted = ml_predict_preferred_category(profile)
            if predicted:
                preferred_category = predicted
        if preferred_category:
            preferred_products = (
                Product.objects.filter(category=preferred_category, is_active=True)
                .order_by("-rating", "name")[:8]
            )
    context = {
        "categories": categories,
        "featured_products": featured_products,
        "preferred_category": preferred_category,
        "preferred_products": preferred_products,
        "fast_selling_products": fast_selling_products,
    }
    return render(request, "ecommercemodule/home.html", context)


def category_list(request):
    categories = Category.objects.prefetch_related("subcategories").all()
    return render(request, "ecommercemodule/category_list.html", {"categories": categories})


def product_list(request, category_slug, subcategory_slug=None):
    category = get_object_or_404(Category, slug=category_slug)
    products = Product.objects.filter(category=category, is_active=True)
    subcategory = None
    if subcategory_slug:
        subcategory = get_object_or_404(
            SubCategory, slug=subcategory_slug, category=category
        )
        products = products.filter(subcategory=subcategory)

    def parse_decimal(param):
        value = request.GET.get(param)
        if value in (None, ""):
            return None
        try:
            decimal_value = Decimal(value)
            if decimal_value < 0:
                return None
            return decimal_value
        except (InvalidOperation, TypeError):
            return None

    min_price = parse_decimal("min_price")
    max_price = parse_decimal("max_price")
    min_rating = parse_decimal("min_rating")
    availability = request.GET.get("availability")
    in_stock_only = request.GET.get("in_stock") == "1"
    sort = request.GET.get("sort")

    if min_price is not None:
        products = products.filter(unit_price__gte=min_price)
    if max_price is not None:
        products = products.filter(unit_price__lte=max_price)
    if min_rating is not None and 0 <= min_rating <= 5:
        products = products.filter(rating__gte=min_rating)
    if availability == "in_stock" or in_stock_only:
        products = products.filter(quantity_on_hand__gt=0)

    sort_map = {
        "price_asc": "unit_price",
        "price_desc": "-unit_price",
        "rating_desc": "-rating",
    }
    if sort in sort_map:
        products = products.order_by(sort_map[sort], "name")

    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_string = query_params.urlencode()
    
    # Get category exploration recommendations for tasteful selling
    exploration_recommendations = ml_category_explore(category_slug, top_n=4)

    return render(
        request,
        "ecommercemodule/product_list.html",
        {
            "category": category,
            "subcategory": subcategory,
            "page_obj": page_obj,
            "paginator": paginator,
            "current_filters": {
                "min_price": min_price,
                "max_price": max_price,
                "min_rating": min_rating,
                "availability": availability,
                "in_stock": availability == "in_stock" or in_stock_only,
                "sort": sort,
            },
            "query_string": query_string,
            "exploration_recommendations": exploration_recommendations,
        },
    )


def product_search(request):
    query = (request.GET.get("q") or "").strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query),
            is_active=True,
        )
    return render(
        request,
        "ecommercemodule/product_search.html",
        {"query": query, "products": products},
    )


def product_detail(request, pk):
    # Annotate product with avg_rating and review_count from Review model
    product = get_object_or_404(
        Product.objects.annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews', distinct=True)
        ),
        pk=pk,
        is_active=True
    )
    
    # Prefetch public reviews with user info
    public_reviews = product.reviews.filter(is_public=True).select_related('user').order_by('-created_at')
    
    # Check if current user has a review and if they've purchased this product
    user_review = None
    review_form = None
    has_purchased = False
    
    if request.user.is_authenticated:
        # Check if user has purchased this product (Order must be PAID)
        profile = _get_or_create_profile(request.user)
        has_purchased = OrderItem.objects.filter(
            order__customer=profile,
            order__status=Order.StatusChoices.PAID,
            product=product
        ).exists()
        
        user_review = product.reviews.filter(user=request.user).first()
        if user_review:
            # If user has a review, pre-populate form for editing
            review_form = ReviewForm(instance=user_review)
        elif has_purchased:
            # Only show form if user has purchased the product
            review_form = ReviewForm()
    
    # Remove non-ML suggestions - only show ML-based recommendations
    suggested_products = []
    # Frequently bought together via association rules (ML-based only)
    fbt_products = list(ml_fbt(product, top_n=4))
    form = AddToCartForm()
    quantity_widget = form.fields["quantity"].widget
    quantity_widget.attrs["class"] = "form-control form-control-lg text-center"
    if product.quantity_on_hand > 0:
        quantity_widget.attrs["max"] = product.quantity_on_hand
    
    return render(
        request,
        "ecommercemodule/product_detail.html",
        {
            "product": product,
            "suggested_products": suggested_products,
            "fbt_products": fbt_products,
            "form": form,
            "is_low_stock": 0 < product.quantity_on_hand < 10,
            "public_reviews": public_reviews,
            "user_review": user_review,
            "review_form": review_form,
            "has_purchased": has_purchased,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("ecommercemodule:home")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Customer.objects.get_or_create(user=user)
            login(request, user)
            messages.success(request, "Welcome to AuroraMart! Please complete your profile to get personalized recommendations.")
            return redirect("ecommercemodule:complete_profile")
    else:
        form = RegistrationForm()
    return render(request, "ecommercemodule/register.html", {"form": form})


@login_required
def complete_profile(request):
    profile = _get_or_create_profile(request.user)
    
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=profile)
        if form.is_valid():
            customer = form.save()
            
            predicted_category = ml_predict_preferred_category(customer)
            if predicted_category:
                customer.preferred_category = predicted_category
                customer.save()
                messages.success(
                    request, 
                    f"Profile completed! We've personalized your experience with {predicted_category.name} products."
                )
            else:
                messages.success(request, "Profile completed successfully!")
            
            return redirect("ecommercemodule:home")
    else:
        form = CustomerForm(instance=profile)
    
    return render(request, "ecommercemodule/complete_profile.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("ecommercemodule:home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        redirect_to = _safe_redirect(request, reverse("ecommercemodule:home"))
        return redirect(redirect_to)
    return render(request, "ecommercemodule/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("ecommercemodule:home")


@login_required
def profile_view(request):
    from admin_panel.models import VoucherAssignment
    from django.utils import timezone
    
    profile = _get_or_create_profile(request.user)
    saved_addresses = CustomerAddress.objects.filter(customer=profile).order_by('-is_default', '-updated_at')
    
    # Get vouchers (both valid and expired for display)
    now = timezone.now()
    voucher_assignments = VoucherAssignment.objects.filter(
        customer=profile
    ).select_related('voucher').order_by('-assigned_at')
    
    # Categorize vouchers
    available_vouchers = [v for v in voucher_assignments if not v.used and v.expires_at > now]
    used_vouchers = [v for v in voucher_assignments if v.used]
    expired_vouchers = [v for v in voucher_assignments if not v.used and v.expires_at <= now]
    
    return render(request, "ecommercemodule/profile.html", {
        "profile": profile,
        "saved_addresses": saved_addresses,
        "available_vouchers": available_vouchers,
        "used_vouchers": used_vouchers,
        "expired_vouchers": expired_vouchers,
    })


@login_required
def profile_update(request):
    profile = _get_or_create_profile(request.user)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=profile)
        if form.is_valid():
            customer = form.save()
            
            # Re-predict preferred category based on updated profile
            predicted_category = ml_predict_preferred_category(customer)
            if predicted_category:
                customer.preferred_category = predicted_category
                customer.save()
                messages.success(request, "Profile updated successfully! Your preferred category has been updated.")
            else:
                messages.success(request, "Profile updated successfully!")
            
            return redirect("ecommercemodule:profile")
    else:
        form = CustomerForm(instance=profile)
    return render(
        request,
        "ecommercemodule/profile_update.html",
        {"form": form},
    )


@login_required
@require_POST
def deactivate_account(request):
    """Permanently delete user account and all related data.
    This action is irreversible - all customer data, orders, reviews, etc. will be deleted.
    """
    user = request.user
    username = user.username
    
    # Log out first
    logout(request)
    
    # Permanently delete the user (CASCADE will delete related Customer, Orders, Reviews, etc.)
    user.delete()
    
    messages.success(
        request, 
        f"Account '{username}' has been permanently deleted. All your data has been removed."
    )
    return redirect("ecommercemodule:home")


@login_required
def order_history(request):
    from django.core.paginator import Paginator
    profile = _get_or_create_profile(request.user)
    orders = profile.orders.prefetch_related("items__product").order_by("-created_at")
    
    # Pagination - 10 orders per page
    paginator = Paginator(orders, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, "ecommercemodule/order_history.html", {"page_obj": page_obj})


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    form = AddToCartForm(request.POST)
    fallback = reverse("ecommercemodule:product_detail", args=[product.pk])
    if not form.is_valid():
        messages.error(request, "Please provide a valid quantity.")
        return redirect(_safe_redirect(request, fallback))

    quantity = form.cleaned_data["quantity"]
    if quantity > product.quantity_on_hand:
        messages.error(request, "Requested quantity exceeds available stock.")
        return redirect(_safe_redirect(request, fallback))

    cart = _ensure_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    if not created:
        new_quantity = cart_item.quantity + quantity
        if new_quantity > product.quantity_on_hand:
            messages.error(request, "Requested quantity exceeds available stock.")
            return redirect(_safe_redirect(request, fallback))
        cart_item.quantity = new_quantity
    cart_item.save()
    messages.success(request, f"Added {quantity} × {product.name} to your cart.")
    return redirect(_safe_redirect(request, fallback))


def view_cart(request):
    cart = _ensure_cart(request)
    cart_total, item_count, items = _cart_overview(cart)
    rows = []

    for item in items:
        form = CartItemUpdateForm(initial={"quantity": item.quantity})
        widget_attrs = form.fields["quantity"].widget.attrs
        max_stock = max(item.product.quantity_on_hand, item.quantity)
        widget_attrs["max"] = max_stock
        widget_attrs["min"] = 0
        widget_attrs["step"] = 1
        widget_attrs["class"] = "form-control form-control-sm text-center"
        rows.append((item, form))
    
    # Add-on suggestions based on current basket using ML recommendations only
    addon_products = []
    if items:
        try:
            # Use ML cart recommendations based on current basket
            addon_products = list(
                ml_cart_recs([i.product for i in items], top_n=4)
            )
        except Exception:
            # No fallback - only show ML recommendations
            addon_products = []
    
    return render(
        request,
        "ecommercemodule/cart.html",
        {
            "cart": cart,
            "rows": rows,
            "cart_total": cart_total,
            "suggested_products": addon_products,
            "item_count": item_count,
        },
    )


@require_POST
def update_cart_item(request, cart_item_id):
    cart = _ensure_cart(request)
    cart_item = get_object_or_404(CartItem, pk=cart_item_id)
    if cart_item.cart_id != cart.id:
        raise Http404
    
    form = CartItemUpdateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid quantity.")
        return redirect("ecommercemodule:view_cart")
    
    quantity = form.cleaned_data["quantity"]
    product_name = cart_item.product.name
    
    if quantity == 0:
        cart_item.delete()
        messages.info(request, f"Removed {product_name} from cart.")
        return redirect("ecommercemodule:view_cart")
    
    if quantity > cart_item.product.quantity_on_hand:
        messages.error(request, f"Requested quantity for {product_name} exceeds available stock.")
        return redirect("ecommercemodule:view_cart")
    
    cart_item.quantity = quantity
    cart_item.save()
    messages.success(request, f"Updated {product_name} quantity to {quantity}.")
    return redirect("ecommercemodule:view_cart")


@require_POST
def remove_from_cart(request, cart_item_id):
    cart = _ensure_cart(request)
    cart_item = get_object_or_404(CartItem, pk=cart_item_id)
    if cart_item.cart_id != cart.id:
        raise Http404
    
    product_name = cart_item.product.name
    cart_item.delete()
    messages.info(request, f"Removed {product_name} from cart.")
    return redirect("ecommercemodule:view_cart")


def perform_checkout(payload: dict):
    """
    Placeholder function to process checkout payment and create order.
    
    In production, this would:
    - Integrate with a payment gateway (Stripe, PayPal, etc.)
    - Verify payment success
    - Create Order and OrderItem records
    - Update product inventory
    - Send confirmation emails
    
    Args:
        payload: Dictionary containing:
            - customer_info: recipient_name, mobile_number, email, postal_code, 
                           address_line1, address_line2, delivery_notes
            - payment_info: cardholder_name, card_number (masked), expiry, cvv
            - order_info: items, cart_total, customer_profile
    
    Returns:
        order_id (int): The created order ID on success
    
    Raises:
        Exception: On payment or order creation failure
    """
    # TODO: Integrate with real payment gateway
    print("=" * 60)
    print("CHECKOUT PAYLOAD (Development Mode)")
    print("=" * 60)
    
    # Customer/Delivery Information
    print("\n[DELIVERY INFORMATION]")
    customer_info = payload.get("customer_info", {})
    for key, value in customer_info.items():
        print(f"  {key}: {value}")
    
    # Payment Information (with masked card number)
    print("\n[PAYMENT INFORMATION]")
    payment_info = payload.get("payment_info", {})
    for key, value in payment_info.items():
        if key == "card_number":
            # Mask all but last 4 digits
            print(f"  {key}: **** **** **** {value[-4:]}")
        elif key == "cvv":
            print(f"  {key}: ***")
        else:
            print(f"  {key}: {value}")
    
    # Order Summary
    print("\n[ORDER SUMMARY]")
    order_info = payload.get("order_info", {})
    print(f"  Total Amount: ${order_info.get('cart_total', 0):.2f}")
    print(f"  Number of Items: {len(order_info.get('items', []))}")
    
    print("\n" + "=" * 60)
    print("Note: Payment processing is simulated in development mode.")
    print("=" * 60 + "\n")
    
    # In production, return the created order_id
    # For now, return None to indicate success without actual order creation
    return None


@login_required
def checkout(request):
    """
    Handle checkout process with comprehensive form validation.
    
    GET: Display checkout form with cart summary
    POST: Validate form, process payment, create order
    """
    cart = _ensure_cart(request)
    items = list(cart.items.select_related("product"))
    
    # Ensure cart is not empty
    if not items:
        messages.error(request, "Your cart is empty. Please add items before checking out.")
        return redirect("ecommercemodule:view_cart")
    
    # Calculate cart total
    cart_total = sum(
        (item.product.unit_price * item.quantity for item in items),
        Decimal("0.00")
    )
    
    # Get user profile (needed for both GET and POST)
    profile = _get_or_create_profile(request.user)
    
    # Initialize discount variables
    voucher_discount = Decimal("0.00")
    applied_voucher = None
    final_total = cart_total
    
    # Handle form submission
    if request.method == "POST":
        # Check if this is just a voucher application (not final checkout)
        apply_voucher_only = request.POST.get('apply_voucher') == 'true'
        
        form = CheckoutForm(request.POST)
        
        # Validate and apply voucher if provided
        voucher_code = request.POST.get("voucher_code", "").strip()
        if voucher_code:
                from admin_panel.models import VoucherAssignment
                from django.utils import timezone
                
                try:
                    voucher_assignment = VoucherAssignment.objects.select_related('voucher').get(
                        voucher__code=voucher_code,
                        customer=profile,
                        used=False
                    )
                    
                    # Check if expired
                    if voucher_assignment.expires_at <= timezone.now():
                        messages.error(request, f"Voucher code '{voucher_code}' has expired.")
                    else:
                        # Calculate discount
                        percent_off = voucher_assignment.voucher.percent_off
                        cap_amount = voucher_assignment.voucher.cap_amount
                        
                        voucher_discount = (cart_total * percent_off / Decimal("100")).quantize(Decimal("0.01"))
                        if cap_amount > 0 and voucher_discount > cap_amount:
                            voucher_discount = cap_amount
                        
                        final_total = cart_total - voucher_discount
                        applied_voucher = voucher_assignment
                        messages.success(request, f"Voucher '{voucher_code}' applied! You saved ${voucher_discount:.2f} ({percent_off}% off)")
                        
                except VoucherAssignment.DoesNotExist:
                    messages.error(request, f"Invalid voucher code '{voucher_code}' or voucher not assigned to you.")
        else:
            final_total = cart_total
        
        # If this is just applying voucher, re-render the form with discount shown
        if apply_voucher_only:
            # Pre-fill form with submitted data for re-display
            form = CheckoutForm(request.POST)
            saved_addresses = CustomerAddress.objects.filter(customer=profile).order_by('-is_default', '-updated_at')
            from admin_panel.models import VoucherAssignment
            from django.utils import timezone
            available_vouchers = VoucherAssignment.objects.select_related('voucher').filter(
                customer=profile,
                used=False,
                expires_at__gt=timezone.now()
            ).order_by('expires_at')
            
            context = {
                "form": form,
                "items": items,
                "cart_total": cart_total,
                "voucher_discount": voucher_discount,
                "final_total": final_total,
                "item_count": sum(item.quantity for item in items),
                "saved_addresses": saved_addresses,
                "available_vouchers": available_vouchers,
            }
            return render(request, "ecommercemodule/checkout.html", context)
        
        if form.is_valid():
            # Check stock availability one more time before processing
            with transaction.atomic():
                for item in items:
                    if item.quantity > item.product.quantity_on_hand:
                        messages.error(
                            request,
                            f"Sorry, {item.product.name} is out of stock or has insufficient quantity. "
                            f"Please adjust your cart."
                        )
                        return redirect("ecommercemodule:view_cart")
                
                # Build payload with cleaned form data
                payload = {
                    "customer_info": {
                        "recipient_name": form.cleaned_data["recipient_name"],
                        "mobile_number": form.cleaned_data["mobile_number"],
                        "email": form.cleaned_data.get("email", ""),
                        "postal_code": form.cleaned_data["postal_code"],
                        "address_line1": form.cleaned_data["address_line1"],
                        "address_line2": form.cleaned_data.get("address_line2", ""),
                        "delivery_notes": form.cleaned_data.get("delivery_notes", ""),
                    },
                    "payment_info": {
                        "cardholder_name": form.cleaned_data["cardholder_name"],
                        "card_number": form.cleaned_data["card_number"],
                        "expiry": form.cleaned_data["expiry"],
                        "cvv": form.cleaned_data["cvv"],
                    },
                    "order_info": {
                        "items": items,
                        "cart_total": final_total,  # Use final_total for payment processing
                        "customer_profile": _get_or_create_profile(request.user),
                    }
                }
                
                try:
                    # Process checkout (placeholder - will integrate with payment gateway later)
                    order_id = perform_checkout(payload)
                    
                    # Create order record with PAID status (since checkout is successful)
                    profile = _get_or_create_profile(request.user)
                    order = Order.objects.create(
                        customer=profile,
                        total_amount=final_total,  # Use final_total (after voucher discount)
                        status=Order.StatusChoices.PAID,  # Set status to PAID automatically
                    )
                    
                    # Mark voucher as used if applied
                    if applied_voucher:
                        applied_voucher.used = True
                        applied_voucher.save()
                    
                    # Create order items
                    order_items = [
                        OrderItem(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            unit_price=item.product.unit_price,
                        )
                        for item in items
                    ]
                    OrderItem.objects.bulk_create(order_items)
                    
                    #-m new stuff here
                    # Create outgoing inventory history entries for each order item
                    try:
                        from admin_panel.models import InventoryHistory

                        for oi in order_items:
                            try:
                                InventoryHistory.objects.create(
                                    product=oi.product,
                                    movement_type='outgoing',
                                    quantity=oi.quantity,
                                    reference_id=order.pk,
                                    notes=f'Outgoing from order {order.pk}'
                                )
                            except Exception:
                                # Continue on individual failures
                                continue
                    except Exception:
                        # If admin_panel.models isn't importable, skip history creation
                        pass
                    # -m new stuff ends here
                    
                    # Update product inventory
                    for item in items:
                        Product.objects.select_for_update().filter(pk=item.product.pk).update(
                            quantity_on_hand=F("quantity_on_hand") - item.quantity
                        )
                    
                    # Save address if requested
                    if form.cleaned_data.get("save_address"):
                        CustomerAddress.objects.create(
                            customer=profile,
                            label=form.cleaned_data.get("address_label", ""),
                            recipient_name=form.cleaned_data["recipient_name"],
                            mobile_number=form.cleaned_data["mobile_number"],
                            email=form.cleaned_data.get("email", ""),
                            postal_code=form.cleaned_data["postal_code"],
                            address_line1=form.cleaned_data["address_line1"],
                            address_line2=form.cleaned_data.get("address_line2", ""),
                            delivery_notes=form.cleaned_data.get("delivery_notes", ""),
                            is_default=form.cleaned_data.get("set_as_default", False)
                        )
                    
                    # Clear the cart
                    cart.items.all().delete()
                    
                    # Success message and redirect
                    messages.success(
                        request,
                        f"Order placed successfully! Your order number is #{order.pk}."
                    )
                    return redirect("ecommercemodule:order_success", order_id=order.pk)
                    
                except Exception as e:
                    # Handle payment or order creation errors
                    messages.error(
                        request,
                        f"There was an error processing your order: {str(e)}. "
                        f"Please try again or contact support."
                    )
                    # Don't clear the form so user can retry
        else:
            # Form validation failed - errors will be displayed inline
            messages.error(
                request,
                "Please correct the errors below and try again."
            )
    else:
        # GET request - display empty form
        # Pre-fill with user profile data if available
        initial_data = {}
        
        # Try to load default address first
        default_address = CustomerAddress.objects.filter(
            customer=profile,
            is_default=True
        ).first()
        
        if default_address:
            # Pre-fill from saved default address
            initial_data["recipient_name"] = default_address.recipient_name
            initial_data["mobile_number"] = default_address.mobile_number
            initial_data["email"] = default_address.email or request.user.email
            initial_data["postal_code"] = default_address.postal_code
            initial_data["address_line1"] = default_address.address_line1
            initial_data["address_line2"] = default_address.address_line2 or ""
            initial_data["delivery_notes"] = default_address.delivery_notes or ""
        else:
            # Fall back to user profile data
            if request.user.email:
                initial_data["email"] = request.user.email
            if request.user.first_name and request.user.last_name:
                initial_data["recipient_name"] = f"{request.user.first_name} {request.user.last_name}"
            elif request.user.username:
                initial_data["recipient_name"] = request.user.username
        
        form = CheckoutForm(initial=initial_data)
    
    # Get saved addresses for display
    saved_addresses = CustomerAddress.objects.filter(customer=profile).order_by('-is_default', '-updated_at')
    
    # Get available vouchers for display
    from admin_panel.models import VoucherAssignment
    from django.utils import timezone
    available_vouchers = VoucherAssignment.objects.select_related('voucher').filter(
        customer=profile,
        used=False,
        expires_at__gt=timezone.now()
    ).order_by('expires_at')
    
    context = {
        "form": form,
        "items": items,
        "cart_total": cart_total,
        "voucher_discount": voucher_discount,
        "final_total": final_total,
        "item_count": sum(item.quantity for item in items),
        "saved_addresses": saved_addresses,
        "available_vouchers": available_vouchers,
    }
    
    return render(request, "ecommercemodule/checkout.html", context)


@login_required
def order_success(request, order_id):
    profile = _get_or_create_profile(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        customer=profile,
    )
    return render(request, "ecommercemodule/order_success.html", {"order": order})


@login_required
def order_detail(request, order_id):
    profile = _get_or_create_profile(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        customer=profile,
    )
    
    # Get user's reviews for products in this order
    product_ids = [item.product.id for item in order.items.all()]
    user_reviews = {
        review.product_id: review 
        for review in Review.objects.filter(user=request.user, product_id__in=product_ids)
    }
    
    # Attach review status to each order item
    for item in order.items.all():
        item.user_review = user_reviews.get(item.product.id)
    
    return render(request, "ecommercemodule/order_detail.html", {
        "order": order,
        "user_reviews": user_reviews,
    })


@login_required
@require_POST
def buy_again(request, order_id):
    """
    Prepare items from a past order for immediate checkout.
    Validates stock availability and redirects to dedicated buy-again checkout.
    """
    profile = _get_or_create_profile(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        customer=profile,
    )
    
    # Track available items for checkout
    available_items = []
    out_of_stock_items = []
    inactive_items = []
    adjusted_items = []
    
    for order_item in order.items.all():
        product = order_item.product
        requested_qty = order_item.quantity
        
        # Check if product is still active
        if not product.is_active:
            inactive_items.append(product.name)
            continue
        
        # Check stock availability
        if product.quantity_on_hand <= 0:
            out_of_stock_items.append(product.name)
            continue
        
        # Adjust quantity if not enough stock
        available_qty = min(requested_qty, product.quantity_on_hand)
        
        available_items.append({
            'product_id': product.id,
            'quantity': available_qty,
            'original_quantity': requested_qty
        })
        
        if available_qty < requested_qty:
            adjusted_items.append({
                'name': product.name,
                'requested': requested_qty,
                'available': available_qty
            })
    
    # Build user-friendly messages
    if adjusted_items:
        for item in adjusted_items:
            messages.warning(
                request,
                f"⚠ {item['name']}: Only {item['available']} unit(s) available (you originally ordered {item['requested']})"
            )
    
    if out_of_stock_items:
        if len(out_of_stock_items) == 1:
            messages.error(request, f"✗ {out_of_stock_items[0]} is currently out of stock.")
        else:
            messages.error(request, f"✗ {len(out_of_stock_items)} item(s) are out of stock: {', '.join(out_of_stock_items[:3])}{'...' if len(out_of_stock_items) > 3 else ''}")
    
    if inactive_items:
        if len(inactive_items) == 1:
            messages.info(request, f"ℹ {inactive_items[0]} is no longer available.")
        else:
            messages.info(request, f"ℹ {len(inactive_items)} item(s) are no longer available.")
    
    # If nothing is available
    if not available_items:
        messages.warning(request, "Unable to re-order. All items are either out of stock or no longer available.")
        return redirect('ecommercemodule:order_detail', order_id=order_id)
    
    # Store buy-again items in session for checkout
    request.session['buy_again_items'] = available_items
    request.session['buy_again_order_id'] = order_id
    
    # Redirect to buy-again checkout
    return redirect('ecommercemodule:buy_again_checkout')


@login_required
def buy_again_checkout(request):
    """
    Dedicated checkout for Buy Again orders.
    Only processes items from the specific buy-again order, not the cart.
    """
    # Get buy-again items from session
    buy_again_items = request.session.get('buy_again_items')
    buy_again_order_id = request.session.get('buy_again_order_id')
    
    if not buy_again_items:
        messages.error(request, "No items to checkout. Please select a past order to buy again.")
        return redirect("ecommercemodule:order_history")
    
    # Fetch products and build items list
    items_data = []
    total_amount = Decimal("0.00")
    
    for item_info in buy_again_items:
        product = get_object_or_404(Product, pk=item_info['product_id'])
        quantity = item_info['quantity']
        
        # Verify stock is still available
        if product.quantity_on_hand < quantity:
            messages.error(
                request,
                f"Stock availability changed for {product.name}. Please try again."
            )
            # Clear session and redirect back
            request.session.pop('buy_again_items', None)
            request.session.pop('buy_again_order_id', None)
            return redirect('ecommercemodule:order_detail', order_id=buy_again_order_id)
        
        item_total = product.unit_price * quantity
        total_amount += item_total
        
        items_data.append({
            'product': product,
            'quantity': quantity,
            'item_total': item_total
        })
    
    # Handle form submission
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        
        if form.is_valid():
            # Process the order
            with transaction.atomic():
                # Double-check stock availability
                for item_data in items_data:
                    product = item_data['product']
                    quantity = item_data['quantity']
                    
                    if quantity > product.quantity_on_hand:
                        messages.error(
                            request,
                            f"Sorry, {product.name} is out of stock or has insufficient quantity."
                        )
                        return redirect("ecommercemodule:order_history")
                
                # Build payload
                payload = {
                    "customer_info": {
                        "recipient_name": form.cleaned_data["recipient_name"],
                        "mobile_number": form.cleaned_data["mobile_number"],
                        "email": form.cleaned_data.get("email", ""),
                        "postal_code": form.cleaned_data["postal_code"],
                        "address_line1": form.cleaned_data["address_line1"],
                        "address_line2": form.cleaned_data.get("address_line2", ""),
                        "delivery_notes": form.cleaned_data.get("delivery_notes", ""),
                    },
                    "payment_info": {
                        "cardholder_name": form.cleaned_data["cardholder_name"],
                        "card_number": form.cleaned_data["card_number"],
                        "expiry": form.cleaned_data["expiry"],
                        "cvv": form.cleaned_data["cvv"],
                    },
                    "order_info": {
                        "items": items_data,
                        "cart_total": total_amount,
                        "customer_profile": _get_or_create_profile(request.user),
                    }
                }
                
                try:
                    # Process checkout
                    order_id = perform_checkout(payload)
                    
                    # Create order record with PAID status
                    profile = _get_or_create_profile(request.user)
                    order = Order.objects.create(
                        customer=profile,
                        total_amount=total_amount,
                        status=Order.StatusChoices.PAID,
                    )
                    
                    # Create order items
                    order_items = [
                        OrderItem(
                            order=order,
                            product=item_data['product'],
                            quantity=item_data['quantity'],
                            unit_price=item_data['product'].unit_price,
                        )
                        for item_data in items_data
                    ]
                    OrderItem.objects.bulk_create(order_items)
                    
                    # Update product inventory
                    for item_data in items_data:
                        Product.objects.select_for_update().filter(pk=item_data['product'].pk).update(
                            quantity_on_hand=F("quantity_on_hand") - item_data['quantity']
                        )
                    
                    # Save address if requested
                    if form.cleaned_data.get("save_address"):
                        CustomerAddress.objects.create(
                            customer=profile,
                            label=form.cleaned_data.get("address_label", ""),
                            recipient_name=form.cleaned_data["recipient_name"],
                            mobile_number=form.cleaned_data["mobile_number"],
                            email=form.cleaned_data.get("email", ""),
                            postal_code=form.cleaned_data["postal_code"],
                            address_line1=form.cleaned_data["address_line1"],
                            address_line2=form.cleaned_data.get("address_line2", ""),
                            delivery_notes=form.cleaned_data.get("delivery_notes", ""),
                            is_default=form.cleaned_data.get("set_as_default", False)
                        )
                    
                    # Clear buy-again session data
                    request.session.pop('buy_again_items', None)
                    request.session.pop('buy_again_order_id', None)
                    
                    # Success message and redirect
                    messages.success(
                        request,
                        f"Order placed successfully! Your order number is #{order.pk}."
                    )
                    return redirect("ecommercemodule:order_success", order_id=order.pk)
                    
                except Exception as e:
                    messages.error(
                        request,
                        f"There was an error processing your order: {str(e)}. Please try again."
                    )
        else:
            messages.error(request, "Please correct the errors below and try again.")
    else:
        # GET request - pre-fill form with user data
        profile = _get_or_create_profile(request.user)
        initial_data = {}
        
        # Try to load default address first
        default_address = CustomerAddress.objects.filter(
            customer=profile,
            is_default=True
        ).first()
        
        if default_address:
            # Pre-fill from saved default address
            initial_data["recipient_name"] = default_address.recipient_name
            initial_data["mobile_number"] = default_address.mobile_number
            initial_data["email"] = default_address.email or request.user.email
            initial_data["postal_code"] = default_address.postal_code
            initial_data["address_line1"] = default_address.address_line1
            initial_data["address_line2"] = default_address.address_line2 or ""
            initial_data["delivery_notes"] = default_address.delivery_notes or ""
        else:
            # Fall back to user profile data
            if request.user.email:
                initial_data["email"] = request.user.email
            if request.user.first_name and request.user.last_name:
                initial_data["recipient_name"] = f"{request.user.first_name} {request.user.last_name}"
            elif request.user.username:
                initial_data["recipient_name"] = request.user.username
        
        form = CheckoutForm(initial=initial_data)
    
    # Get saved addresses for display
    saved_addresses = CustomerAddress.objects.filter(customer=profile).order_by('-is_default', '-updated_at')
    
    context = {
        "form": form,
        "items": items_data,
        "cart_total": total_amount,
        "is_buy_again": True,  # Flag to distinguish from regular checkout
        "saved_addresses": saved_addresses,
    }
    
    return render(request, "ecommercemodule/checkout.html", context)


class AuthFormMixin:
    title = ""
    submit_label = "Submit"
    template_name = "ecommercemodule/auth_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title
        ctx["submit_label"] = self.submit_label
        return ctx

class PasswordResetRequestView(AuthFormMixin, PasswordResetView):
    title = "Reset Password"
    submit_label = "Send Reset Link"
    form_class = StorePasswordResetForm
    template_name = "ecommercemodule/auth_form.html"
    email_template_name = "ecommercemodule/email/password_reset_email.txt"
    html_email_template_name = "ecommercemodule/email/password_reset_email.html"
    subject_template_name = "ecommercemodule/email/password_reset_subject.txt"
    success_url = reverse_lazy("ecommercemodule:login")

    def form_valid(self, form):
        messages.info(self.request, "If that email exists, we sent reset instructions.")
        return super().form_valid(form)

class PasswordResetConfirmSlim(AuthFormMixin, PasswordResetConfirmView):
    title = "Choose New Password"
    submit_label = "Set Password"
    success_url = reverse_lazy("ecommercemodule:login")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been set. Please log in.")
        return super().form_valid(form)

class PasswordChangeSlim(AuthFormMixin, LoginRequiredMixin, PasswordChangeView):
    title = "Change Password"
    submit_label = "Update Password"
    success_url = reverse_lazy("ecommercemodule:profile")

    def form_valid(self, form):
        messages.success(self.request, "Password updated successfully.")
        return super().form_valid(form)

def product_search(request):
    query = (request.GET.get("q") or "").strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(sku__icontains=query),
            is_active=True,
        )
    return render(
        request,
        "ecommercemodule/product_search.html",
        {"query": query, "products": products},
    )


@login_required
@require_POST
def review_save(request, product_id):
    """Create or update the current user's review for a product"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    
    # Verify user has purchased this product
    profile = _get_or_create_profile(request.user)
    has_purchased = OrderItem.objects.filter(
        order__customer=profile,
        order__status=Order.StatusChoices.PAID,
        product=product
    ).exists()
    
    if not has_purchased:
        messages.error(request, "You can only review products you have purchased.")
        # Try to redirect back to referrer
        referer = request.META.get('HTTP_REFERER')
        if referer and 'order' in referer:
            return redirect(referer)
        return redirect('ecommercemodule:product_detail', pk=product_id)
    
    # Check if user already has a review
    review = Review.objects.filter(product=product, user=request.user).first()
    
    form = ReviewForm(request.POST, instance=review)
    
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_public = True  # Default to public
        review.save()
        
        if form.instance.pk:
            messages.success(request, "Your review has been updated successfully!")
        else:
            messages.success(request, "Thank you for your review!")
    else:
        # Show form errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    
    # Redirect back to referrer (order detail) or product detail
    referer = request.META.get('HTTP_REFERER')
    if referer and 'order' in referer:
        return redirect(referer)
    return redirect('ecommercemodule:product_detail', pk=product_id)


@login_required
@require_POST
def review_delete(request, product_id):
    """Delete the current user's review for a product"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    
    review = get_object_or_404(Review, product=product, user=request.user)
    review.delete()
    
    messages.info(request, "Your review has been deleted.")
    
    # Redirect back to referrer (order detail) or product detail
    referer = request.META.get('HTTP_REFERER')
    if referer and 'order' in referer:
        return redirect(referer)
    return redirect('ecommercemodule:product_detail', pk=product_id)


@login_required
def address_add(request):
    """Add a new saved address"""
    profile = _get_or_create_profile(request.user)
    
    if request.method == 'POST':
        form = CustomerAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.customer = profile
            address.save()
            messages.success(request, "Address saved successfully!")
            return redirect('ecommercemodule:profile')
    else:
        # Pre-fill with user data
        initial_data = {
            'recipient_name': request.user.get_full_name() or request.user.username,
            'email': request.user.email
        }
        form = CustomerAddressForm(initial=initial_data)
    
    return render(request, 'ecommercemodule/address_form.html', {
        'form': form,
        'title': 'Add New Address'
    })


@login_required
def address_edit(request, address_id):
    """Edit an existing saved address"""
    profile = _get_or_create_profile(request.user)
    address = get_object_or_404(CustomerAddress, pk=address_id, customer=profile)
    
    if request.method == 'POST':
        form = CustomerAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully!")
            return redirect('ecommercemodule:profile')
    else:
        form = CustomerAddressForm(instance=address)
    
    return render(request, 'ecommercemodule/address_form.html', {
        'form': form,
        'title': 'Edit Address',
        'address': address
    })


@login_required
@require_POST
def address_delete(request, address_id):
    """Delete a saved address"""
    profile = _get_or_create_profile(request.user)
    address = get_object_or_404(CustomerAddress, pk=address_id, customer=profile)
    
    address_label = address.label or 'Address'
    address.delete()
    messages.info(request, f"{address_label} has been deleted.")
    return redirect('ecommercemodule:profile')


@login_required
@require_POST
def address_set_default(request, address_id):
    """Set an address as the default"""
    profile = _get_or_create_profile(request.user)
    address = get_object_or_404(CustomerAddress, pk=address_id, customer=profile)
    
    # Unset other defaults
    CustomerAddress.objects.filter(customer=profile, is_default=True).update(is_default=False)
    
    # Set this one as default
    address.is_default = True
    address.save()
    
    messages.success(request, f"{address.label or 'Address'} set as default.")
    return redirect('ecommercemodule:profile')


@login_required
@require_POST
def validate_voucher(request):
    """
    AJAX endpoint to validate voucher code and return discount information.
    Returns JSON with validation result and discount details.
    """
    from admin_panel.models import VoucherAssignment
    from django.utils import timezone
    
    voucher_code = request.POST.get('voucher_code', '').strip().upper()
    
    if not voucher_code:
        return JsonResponse({
            'valid': False,
            'message': 'Please enter a voucher code.'
        })
    
    profile = _get_or_create_profile(request.user)
    cart = _ensure_cart(request)
    
    # Calculate cart total
    items = list(cart.items.select_related("product"))
    cart_total = sum(
        (item.product.unit_price * item.quantity for item in items),
        Decimal("0.00")
    )
    
    try:
        # Find voucher assignment for this user
        voucher_assignment = VoucherAssignment.objects.select_related('voucher').get(
            voucher__code=voucher_code,
            customer=profile,
            used=False
        )
        
        # Check if expired
        now = timezone.now()
        if voucher_assignment.expires_at <= now:
            return JsonResponse({
                'valid': False,
                'message': f"Voucher '{voucher_code}' has expired on {voucher_assignment.expires_at.strftime('%d %b %Y')}."
            })
        
        # Calculate discount
        voucher = voucher_assignment.voucher
        percent_off = voucher.percent_off
        discount_amount = (cart_total * percent_off / 100).quantize(Decimal("0.01"))
        
        # Apply cap if set
        if voucher.cap_amount > 0:
            discount_amount = min(discount_amount, voucher.cap_amount)
        
        return JsonResponse({
            'valid': True,
            'discount': float(discount_amount),
            'percent_off': float(percent_off),
            'cap_amount': float(voucher.cap_amount) if voucher.cap_amount else None,
            'code': voucher_code,
            'expires_at': voucher_assignment.expires_at.strftime('%d %b %Y')
        })
        
    except VoucherAssignment.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'message': f"Invalid voucher code '{voucher_code}' or voucher not assigned to you."
        })



