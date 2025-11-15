from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from .models import TransactionItem, InventoryHistory, InventoryItem


def _handle_outgoing(product, qty, reference_id=None, notes=None):
    """Helper to create InventoryHistory outgoing entry and decrement product stock."""
    try:
        with transaction.atomic():
            InventoryHistory.objects.create(
                product=product,
                movement_type='outgoing',
                quantity=qty,
                reference_id=reference_id,
                notes=notes,
            )

            # Decrement product quantity_on_hand (do not allow negative)
            try:
                new_qty = int(product.quantity_on_hand) - int(qty)
            except Exception:
                new_qty = None

            if new_qty is not None:
                product.quantity_on_hand = max(0, new_qty)
                product.save()

                # Sync InventoryItem if present
                try:
                    inv_item = product.inventory_item
                    inv_item.save()
                except InventoryItem.DoesNotExist:
                    pass
    except Exception:
        # Swallow exceptions to avoid breaking the creator flow; log in production
        pass


@receiver(post_save, sender=TransactionItem)
def create_outgoing_history_on_transaction_item(sender, instance, created, **kwargs):
    if not created:
        return

    reference = getattr(instance.transaction, 'transaction_id', None)
    notes = f'Outgoing from transaction {reference or "-"}'
    _handle_outgoing(instance.product, instance.quantity, reference_id=reference, notes=notes)


# Also listen for front-end orders (OrderItem in ecommercemodule)
try:
    from ecommercemodule.models import OrderItem

    @receiver(post_save, sender=OrderItem)
    def create_outgoing_history_on_order_item(sender, instance, created, **kwargs):
        if not created:
            return

        reference = getattr(instance.order, 'pk', None)
        notes = f'Outgoing from order {reference or "-"}'
        _handle_outgoing(instance.product, instance.quantity, reference_id=reference, notes=notes)
except Exception:
    # If ecommercemodule not importable at import time, skip wiring; apps.ready() will re-import signals
    pass
