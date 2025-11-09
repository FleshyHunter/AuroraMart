from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from auroramart.models import Category, Customer, Product


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
        return f"Order #{self.pk} - {self.customer}"


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

    @property
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
