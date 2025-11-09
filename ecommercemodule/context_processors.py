from django.db.models import Sum

from .models import Cart, Customer


def cart_item_count(request):
    """
    Expose the current cart's total quantity so navigation badges can stay in sync.
    """
    cart = None
    if not hasattr(request, "session"):
        return {"cart_item_count": 0}

    if request.user.is_authenticated:
        profile, _ = Customer.objects.get_or_create(user=request.user)
        cart = Cart.objects.filter(customer=profile).first()
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = Cart.objects.filter(session_key=session_key).first()

    if not cart:
        return {"cart_item_count": 0}

    total = cart.items.aggregate(total=Sum("quantity"))["total"] or 0
    return {"cart_item_count": total}
