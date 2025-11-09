from django.db import models
from django.core.validators import MinValueValidator

from auroramart.models import Product, Customer


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

