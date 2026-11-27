
"""
Checkout business logic for TaskFlow.

Creates simulated orders from validated session
cart data. No real payments are processed.
"""

from decimal import Decimal
from django.db import transaction
from .models import CatalogItem, Order, OrderItem
from .visibility import get_visible_category_ids

class CheckoutError(Exception):
    """
    Raised when a shopping cart cannot be checked out.
    """
    pass


def create_order_from_cart(user, cart):
    """
    Create an order using current database prices.

    The cart must contain validated item IDs and
    quantities, as returned by load_cart().

    Order creation is atomic: either the order and
    every order item are saved, or none are saved.
    """

    if not user.is_authenticated:
        raise CheckoutError(
            "You must be signed in to place an order."
        )

    if not cart:
        raise CheckoutError(
            "Your cart is empty."
        )

    item_ids = [int(item_id) for item_id in cart]

    with transaction.atomic():

        # Retrieve categories belonging to completely
        # active category hierarchies.
        visible_category_ids = get_visible_category_ids()

        # Retrieve and lock only services eligible for checkout.
        items = list(
            CatalogItem.objects
            .select_for_update()
            .filter(
                pk__in=item_ids,
                is_active=True,
                is_available=True,
                category_id__in=visible_category_ids,
            )
            .order_by("pk")
        )

        # Never silently omit unavailable services.
        if len(items) != len(cart):
            raise CheckoutError(
                "One or more selected services are no "
                "longer available. Please review your cart."
            )

        total_amount = Decimal("0.00")

        for item in items:
            quantity = cart[str(item.pk)]
            total_amount += item.price * quantity

        # Create the order.
        order = Order.objects.create(
            user=user,
            total_amount=total_amount,
            status=Order.OrderStatus.PLACED,
        )

        # Store historical names, quantities, and prices.
        order_items = [
            OrderItem(
                order=order,
                catalog_item=item,
                item_name=item.name,
                quantity=cart[str(item.pk)],
                unit_price=item.price,
            )
            for item in items
        ]

        OrderItem.objects.bulk_create(order_items)

    return order