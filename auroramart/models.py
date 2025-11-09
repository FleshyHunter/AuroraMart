from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class Category(models.Model):
    """Product category - shared between ecommerce and admin panel"""
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name

class SubCategory(models.Model):
    """Product subcategory - shared between ecommerce and admin panel"""
    category = models.ForeignKey(
        Category, related_name="subcategories", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "SubCategories"
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
    """Product model - shared between ecommerce and admin panel"""
    sku = models.CharField(max_length=64, unique=True, verbose_name="SKU Code")
    name = models.CharField(max_length=255, verbose_name="Product Name")
    description = models.TextField(blank=True, verbose_name="Product Description")
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.PROTECT, verbose_name="Product Category"
    )
    subcategory = models.ForeignKey(
        SubCategory, related_name="products", on_delete=models.PROTECT, verbose_name="Product Subcategory"
    )
    quantity_on_hand = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    reorder_quantity = models.PositiveIntegerField(default=10, validators=[MinValueValidator(0)])
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)]
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=0.0,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name="Product Rating"
    )
    is_active = models.BooleanField(default=True)

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
    """Customer model - shared between ecommerce and admin panel"""
    user = models.OneToOneField(
        User, related_name="customer_profile", on_delete=models.CASCADE, null=True, blank=True
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
        ordering = ["id"]

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
        if self.user:
            return f"Profile for {self.user.username}"
        return f"Customer #{self.pk}"
