from django.contrib import admin
from .models import Order, OrderItem, Cart, CartItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_price', 'line_total')
    can_delete = False

    def line_total(self, obj):
        return f"${obj.line_total:.2f}"
    line_total.short_description = "Line Total"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'created_at', 'status', 'total_amount')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__user__username', 'customer__user__email')
    readonly_fields = ('created_at',)
    inlines = [OrderItemInline]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'session_key', 'created_at', 'item_count')
    search_fields = ('customer__user__username', 'session_key')
    readonly_fields = ('created_at',)

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'quantity', 'added_at')
    search_fields = ('product__name', 'product__sku')
    readonly_fields = ('added_at',)
