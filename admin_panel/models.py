from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid

from auroramart.models import Product, Customer

def generate_voucher_code():
    """Generate a random 8-character voucher code."""
    return uuid.uuid4().hex[:8].upper()

class Transaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transactions')
    transaction_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2) 


class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)


class Inventory(models.Model):
    name = models.CharField(max_length=100)  # e.g., "Main Warehouse"
    items = models.ManyToManyField('InventoryItem', related_name='inventories', blank=True)


class InventoryItem(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='inventory_item')
    quantity_on_hand = models.IntegerField(default=0)
    reorder_quantity = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        self.quantity_on_hand = self.product.quantity_on_hand
        self.reorder_quantity = self.product.reorder_quantity
        super().save(*args, **kwargs)


class IncomingStock(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('received', 'Received'),
    ]
    
    shipment_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='incoming_stock')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order_date = models.DateTimeField(auto_now_add=True)
    confirmation_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Shipment {self.shipment_id} - {self.product.name} ({self.quantity})"


class InventoryHistory(models.Model):
    MOVEMENT_TYPES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]
    
    history_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_history')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reference_id = models.PositiveIntegerField(null=True, blank=True)  # Shipment ID or Transaction ID
    movement_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
 
    def __str__(self):
        return f"History {self.history_id} - {self.product.name} ({self.movement_type}) - {self.quantity}"


class Voucher(models.Model):
    """A voucher that can be distributed to customers.

    - name: human-friendly name (e.g., "Spring Sale 20%")
    - code: short unique code admins can share
    - days_valid: number of days the voucher is valid from assignment
    - percent_off: percentage discount (0-100)
    - cap_amount: maximum discount amount in currency
    """
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, unique=True, default=generate_voucher_code)
    days_valid = models.PositiveIntegerField(default=30, help_text="How many days the voucher is valid from assignment")
    percent_off = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    cap_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.code})"

    def assign_to_customer(self, customer, assigned_at=None):
        """Create a VoucherAssignment for a single customer (idempotent)."""
        if assigned_at is None:
            assigned_at = timezone.now()

        # avoid duplicates for same voucher/customer
        existing = VoucherAssignment.objects.filter(voucher=self, customer=customer).first()
        if existing:
            return existing

        expires_at = assigned_at + timedelta(days=self.days_valid)
        va = VoucherAssignment.objects.create(voucher=self, customer=customer, assigned_at=assigned_at, expires_at=expires_at)
        return va

    def assign_to_customers(self, customers_queryset):
        """Bulk assign to a queryset or iterable of Customer instances. Returns number created."""
        created = 0
        now = timezone.now()
        for c in customers_queryset:
            if not VoucherAssignment.objects.filter(voucher=self, customer=c).exists():
                expires_at = now + timedelta(days=self.days_valid)
                VoucherAssignment.objects.create(voucher=self, customer=c, assigned_at=now, expires_at=expires_at)
                created += 1
        return created


class VoucherAssignment(models.Model):
    """Represents a voucher assigned to a specific customer."""
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='assignments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='voucher_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        unique_together = (('voucher', 'customer'),)
        ordering = ("-assigned_at",)

    def __str__(self):
        return f"{self.voucher.code} -> Customer #{self.customer.pk}"

    def save(self, *args, **kwargs):
        # ensure expires_at is set relative to assigned_at if missing
        if not self.expires_at:
            base = self.assigned_at or timezone.now()
            self.expires_at = base + timedelta(days=self.voucher.days_valid)
        super().save(*args, **kwargs)

