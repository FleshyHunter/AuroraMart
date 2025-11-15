from django.contrib import admin
from .models import Transaction, TransactionItem, IncomingStock, InventoryHistory
from .models import Voucher, VoucherAssignment

# Note: Product and Customer are registered in auroramart/admin.py (shared models)

class TransactionItemInline(admin.TabularInline):
    model = TransactionItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')
    can_delete = False

# Transaction admin
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'customer', 'transaction_date', 'total_amount')
    search_fields = ('customer',)
    inlines = [TransactionItemInline]

# Register Transaction with its admin
admin.site.register(Transaction, TransactionAdmin)


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'percent_off', 'cap_amount', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    list_filter = ('created_at',)
    filter_horizontal = ()


class VoucherAssignmentInline(admin.TabularInline):
    model = VoucherAssignment
    extra = 0
    readonly_fields = ('customer', 'assigned_at', 'expires_at', 'used')
    can_delete = False


@admin.register(VoucherAssignment)
class VoucherAssignmentAdmin(admin.ModelAdmin):
    list_display = ('voucher', 'customer', 'assigned_at', 'expires_at', 'used')
    list_filter = ('used',)
    search_fields = ('voucher__name', 'voucher__code', 'customer__user__username')
    readonly_fields = ('assigned_at',)

@admin.register(IncomingStock)
class IncomingStockAdmin(admin.ModelAdmin):
    list_display = ('shipment_id', 'product', 'quantity', 'status', 'order_date', 'confirmation_date')
    list_filter = ('status', 'order_date')
    search_fields = ('product__name', 'product__sku')
    readonly_fields = ('shipment_id', 'order_date')
    ordering = ('-order_date',)

@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ('history_id', 'product', 'movement_type', 'quantity', 'reference_id', 'movement_date')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('product__name', 'product__sku', 'reference_id')
    readonly_fields = ('history_id', 'movement_date')
    ordering = ('-movement_date',)
