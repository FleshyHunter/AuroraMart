from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from auroramart.models import Category, Customer, Product

User = get_user_model()

# Validators for CustomerAddress
phone_validator = RegexValidator(r'^\+?\d{8,15}$', "Enter a valid phone number.")
postal_validator = RegexValidator(r'^\d{6}$', "Enter a 6-digit Singapore postal code.")


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
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.PAID
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    voucher_code = models.CharField(
        max_length=32, blank=True, null=True, help_text="Applied voucher code"
    )
    voucher_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), 
        validators=[MinValueValidator(0)], help_text="Discount amount from voucher"
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


class Review(models.Model):
    """Per-user product review without modifying Product model"""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    product = models.ForeignKey(
        Product, 
        related_name="reviews", 
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User,
        related_name="reviews",
        on_delete=models.CASCADE
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField(verbose_name="Review")
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        unique_together = [["product", "user"]]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]
    
    def clean(self):
        errors = {}
        if not 1 <= self.rating <= 5:
            errors["rating"] = "Rating must be between 1 and 5."
        if not self.body or not self.body.strip():
            errors["body"] = "Review cannot be empty."
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.user.username}'s review of {self.product.name} ({self.rating}★)"


class CustomerAddress(models.Model):
    """Saved address for customers to reuse at checkout"""
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name="addresses"
    )
    label = models.CharField(
        max_length=50, 
        blank=True,
        help_text="e.g., 'Home' or 'Work'"
    )
    recipient_name = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField(blank=True, null=True)
    postal_code = models.CharField(max_length=6, validators=[postal_validator])
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    delivery_notes = models.TextField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-is_default", "-updated_at"]
        verbose_name = "Customer Address"
        verbose_name_plural = "Customer Addresses"
    
    def clean(self):
        errors = {}
        if not self.recipient_name or not self.recipient_name.strip():
            errors["recipient_name"] = "Recipient name is required."
        if not self.mobile_number or not self.mobile_number.strip():
            errors["mobile_number"] = "Mobile number is required."
        if not self.postal_code or not self.postal_code.strip():
            errors["postal_code"] = "Postal code is required."
        if not self.address_line1 or not self.address_line1.strip():
            errors["address_line1"] = "Address line 1 is required."
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # If this address is being set as default, unset other defaults
        if self.is_default:
            CustomerAddress.objects.filter(
                customer=self.customer,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        label = self.label or "Address"
        return f"{label} ({self.postal_code})"
