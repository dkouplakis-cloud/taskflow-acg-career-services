
"""
Session-based shopping cart utilities for TaskFlow.

The cart stores catalogue item IDs and quantities.
Product details and prices are always retrieved
from the database when needed.
"""

CART_SESSION_KEY = "catalog_cart"
MAX_QUANTITY_PER_ITEM = 10


def load_cart(request):
    """
    Return a validated copy of the session cart.

    Invalid item IDs and quantities are ignored.
    """

    stored_cart = request.session.get(
        CART_SESSION_KEY,
        {}
    )

    if not isinstance(stored_cart, dict):
        return {}

    cart = {}

    for item_id, quantity in stored_cart.items():

        # Session cart keys must be valid item IDs.
        if (
            not isinstance(item_id, str)
            or not item_id.isdecimal()
            or int(item_id) <= 0
        ):
            continue

        # Quantities must be integers within limits.
        # Reject booleans because bool subclasses int.
        if type(quantity) is not int:
            continue

        if not 1 <= quantity <= MAX_QUANTITY_PER_ITEM:
            continue

        cart[str(int(item_id))] = quantity

    return cart


def save_cart(request, cart):
    """
    Save cart contents into the Django session.
    """

    request.session[CART_SESSION_KEY] = cart

    # Explicitly mark the session as changed.
    request.session.modified = True