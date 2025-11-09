from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordChangeView

from .forms import StorePasswordResetForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    AddToCartForm,
    CartItemUpdateForm,
    CheckoutConfirmForm,
    CustomerForm,
    LoginForm,
    ProfileCompletionForm,
    RegistrationForm,
    StorePasswordResetForm,
)
from auroramart.models import Category, Customer, Product, SubCategory
from .models import Cart, CartItem, Order, OrderItem
from auroramart.ml import (
    predict_customer_preferred_category as ml_predict_preferred_category,
    frequently_bought_together as ml_fbt,
    cart_add_on_recommendations as ml_cart_recs,
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
        },
    )


def product_search(request):
    query = (request.GET.get("q") or "").strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
        )
    return render(
        request,
        "ecommercemodule/product_search.html",
        {"query": query, "products": products},
    )


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    suggested_products = (
        Product.objects.filter(subcategory=product.subcategory, is_active=True)
        .exclude(pk=product.pk)[:4]
    )
    # Frequently bought together via association rules (best effort)
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
            "suggested_products": suggested_products,  # TODO: plug ML recommendations here.
            "fbt_products": fbt_products,
            "form": form,
            "is_low_stock": 0 < product.quantity_on_hand < 10,
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
        form = ProfileCompletionForm(request.POST, instance=profile)
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
        form = ProfileCompletionForm(instance=profile)
    
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
    profile = _get_or_create_profile(request.user)
    return render(request, "ecommercemodule/profile.html", {"profile": profile})


@login_required
def profile_update(request):
    profile = _get_or_create_profile(request.user)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
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
    user = request.user
    user.is_active = False
    user.save(update_fields=["is_active"])
    logout(request)
    return render(request, "ecommercemodule/account_deactivated.html")


@login_required
def order_history(request):
    profile = _get_or_create_profile(request.user)
    orders = profile.orders.prefetch_related("items__product")
    return render(request, "ecommercemodule/order_history.html", {"orders": orders})


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
    # Add-on suggestions based on current basket; fallback to generic picks
    addon_products = []
    try:
        addon_products = list(
            ml_cart_recs([i.product for i in items], top_n=4)
        )
    except Exception:
        addon_products = []
    if not addon_products:
        addon_products = list(
            Product.objects.filter(is_active=True)
            .exclude(pk__in=[item.product_id for item in items])[:4]
        )
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


@login_required
def checkout(request):
    cart = _ensure_cart(request)
    items = list(cart.items.select_related("product"))
    if not items:
        messages.error(request, "Your cart is empty.")
        return redirect("ecommercemodule:view_cart")

    if request.method == "POST":
        form = CheckoutConfirmForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                for item in items:
                    if item.quantity > item.product.quantity_on_hand:
                        messages.error(
                            request,
                            f"Not enough stock for {item.product.name}. Please adjust your cart.",
                        )
                        return redirect("ecommercemodule:view_cart")
                total = sum(
                    (item.product.unit_price * item.quantity for item in items),
                    Decimal("0.00"),
                )
                profile = _get_or_create_profile(request.user)
                order = Order.objects.create(
                    customer=profile,
                    total_amount=total,
                )
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
                for item in items:
                    Product.objects.select_for_update().filter(pk=item.product.pk).update(
                        quantity_on_hand=F("quantity_on_hand") - item.quantity
                    )
                cart.items.all().delete()
                messages.success(request, "Order placed successfully.")
                return redirect("ecommercemodule:order_success", order_id=order.pk)
    else:
        form = CheckoutConfirmForm(initial={"confirm": True})
    cart_total = sum(
        (item.product.unit_price * item.quantity for item in items), Decimal("0.00")
    )
    return render(
        request,
        "ecommercemodule/checkout.html",
        {"items": items, "cart_total": cart_total, "form": form},
    )


@login_required
def order_success(request, order_id):
    profile = _get_or_create_profile(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        customer=profile,
    )
    return render(request, "ecommercemodule/order_success.html", {"order": order})


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
    form_class =StorePasswordResetForm
    email_template_name = "ecommercemodule/email/password_reset_email.txt"
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
    template_name = "ecommercemodule/password_change_done.html"

def product_search(request):
    query = (request.GET.get("q") or "").strip()
    products = Product.objects.none()
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            is_active=True,
        )
    return render(
        request,
        "ecommercemodule/product_search.html",
        {"query": query, "products": products},
    )
