
"""
Simulated checkout views for TaskFlow.

No real payments are processed.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from .models import Order
from .cart import CART_SESSION_KEY, load_cart
from .checkout_service import CheckoutError, create_order_from_cart


@login_required
@require_POST
def place_order(request):
    """
    Create a simulated order from the user's cart.

    Clear the cart only after successful order creation.
    """

    cart = load_cart(request)

    try:
        order = create_order_from_cart(
            request.user,
            cart
        )

    except CheckoutError as error:
        messages.error(request, str(error))
        return redirect("catalog:cart")

    # The database transaction has completed successfully.
    request.session.pop(CART_SESSION_KEY, None)

    messages.success(
        request,
        "Your order has been placed successfully."
    )

    return redirect(
        "catalog:order_confirmation",
        order_id=order.pk
    )

@login_required
@require_GET
def order_confirmation(request, order_id):
    """
    Display confirmation details for a completed
    simulated checkout.

    Users may view only their own orders.
    """

    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        pk=order_id,
        user=request.user,
    )

    context = {
        "page_title": f"Order #{order.pk} Confirmation",
        "order": order,
        "order_items": order.items.all(),
    }

    return render(
        request,
        "catalog/order_confirmation.html",
        context
    )

@login_required
@require_GET
def order_history(request):
    """
    Display the authenticated user's simulated
    catalogue orders, newest first.

    Never expose orders belonging to other users.
    """

    # Enforce ownership at the database-query level.
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )

    context = {
        "page_title": "My Orders",
        "orders": orders,
    }

    return render(
        request,
        "catalog/order_history.html",
        context
    )