from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(
        Category, related_name="subcategories", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"], name="unique_subcategory_name_per_category"
            ),
            models.UniqueConstraint(
                fields=["category", "slug"], name="unique_subcategory_slug_per_category"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category.name} / {self.name}"


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.PROTECT
    )
    subcategory = models.ForeignKey(
        SubCategory, related_name="products", on_delete=models.PROTECT
    )
    quantity_on_hand = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    reorder_quantity = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    rating = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["is_active"]),
        ]

    def clean(self):
        errors = {}
        if self.subcategory and self.category and self.subcategory.category_id != self.category_id:
            errors["subcategory"] = "Subcategory must belong to the selected category."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class Customer(models.Model):
    user = models.OneToOneField(
        User, related_name="customer_profile", on_delete=models.CASCADE
    )
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=100, blank=True)
    employment_status = models.CharField(max_length=255, blank=True)
    occupation = models.CharField(max_length=255, blank=True)
    education = models.CharField(max_length=255, blank=True)
    household_size = models.PositiveIntegerField(null=True, blank=True)
    has_children = models.BooleanField(default=False)
    monthly_income_sgd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    preferred_category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["user__username"]

    def clean(self):
        errors = {}
        if self.age is not None and not 18 <= self.age <= 100:
            errors["age"] = "Age must be between 18 and 100."
        if self.household_size is not None and self.household_size < 1:
            errors["household_size"] = "Household size must be at least 1."
        if self.monthly_income_sgd is not None and self.monthly_income_sgd < Decimal("0.00"):
            errors["monthly_income_sgd"] = "Monthly income must be zero or higher."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Profile for {self.user.username}"


class Order(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    customer = models.ForeignKey(
        Customer, related_name="orders", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} - {self.customer.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, related_name="items", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["product__name"]

    def clean(self):
        errors = {}
        if self.quantity < 1:
            errors["quantity"] = "Quantity must be at least 1."
        if self.unit_price < Decimal("0.00"):
            errors["unit_price"] = "Unit price cannot be negative."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"


class Cart(models.Model):
    customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.CASCADE
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(customer__isnull=False),
                name="unique_cart_per_customer",
            ),
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(session_key__isnull=False),
                name="unique_cart_per_session",
            ),
        ]

    def clean(self):
        if not self.customer and not self.session_key:
            raise ValidationError("Cart must be associated with a customer or session key.")
        if self.customer and self.session_key:
            raise ValidationError("Cart cannot reference both a customer and a session.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        owner = self.customer.user.username if self.customer else self.session_key
        return f"Cart for {owner or 'anonymous'}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, related_name="items", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_product_per_cart"
            ),
        ]
        ordering = ["-added_at"]

    def clean(self):
        errors = {}
        if self.quantity < 1:
            errors["quantity"] = "Quantity must be at least 1."
        if self.product and self.quantity > self.product.quantity_on_hand:
            errors["quantity"] = "Requested quantity exceeds current stock."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def line_total(self) -> Decimal:
        return self.product.unit_price * self.quantity

    def __str__(self) -> str:
        return f"{self.product.name} ({self.quantity})"