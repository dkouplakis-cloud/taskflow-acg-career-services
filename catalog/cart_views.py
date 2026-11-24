
"""
Shopping cart views for TaskFlow.

Cart modifications require an authenticated user
and an HTTP POST request.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from decimal import Decimal
from django.shortcuts import render
from django.views.decorators.http import require_safe


from .cart import (
    MAX_QUANTITY_PER_ITEM,
    load_cart,
    save_cart,
)
from .models import CatalogItem


@login_required
@require_POST
def add_to_cart(request, slug):
    """
    Add one available catalogue item to the
    authenticated user's session cart.
    """

    item = get_object_or_404(
        CatalogItem,
        slug=slug,
        is_active=True,
        is_available=True,
        category__is_active=True,
    )

    cart = load_cart(request)
    item_id = str(item.pk)

    current_quantity = cart.get(item_id, 0)

    if current_quantity >= MAX_QUANTITY_PER_ITEM:
        messages.warning(
            request,
            "You have reached the maximum quantity "
            "allowed for this service."
        )

        return redirect(
            "catalog:detail",
            slug=item.slug
        )

    cart[item_id] = current_quantity + 1

    save_cart(request, cart)

    messages.success(
        request,
        f"{item.name} was added to your cart."
    )

    return redirect(
        "catalog:detail",
        slug=item.slug
    )

@login_required
@require_safe
def cart_detail(request):
    """
    Display the authenticated user's shopping cart.

    Retrieve current catalogue information and prices
    from the database rather than trusting session data.
    """

    cart = load_cart(request)

    items = (
        CatalogItem.objects
        .filter(
            pk__in=cart.keys(),
            is_active=True,
            is_available=True,
            category__is_active=True
        )
        .select_related("category")
        .order_by("name", "pk")
    )

    cart_lines = []
    total_amount = Decimal("0.00")
    total_quantity = 0

    for item in items:
        quantity = cart[str(item.pk)]
        subtotal = item.price * quantity

        cart_lines.append({
            "item": item,
            "quantity": quantity,
            "subtotal": subtotal,
        })

        total_amount += subtotal
        total_quantity += quantity

    context = {
        "page_title": "My Cart",
        "cart_lines": cart_lines,
        "total_amount": total_amount,
        "total_quantity": total_quantity,
    }

    return render(
        request,
        "catalog/cart_detail.html",
        context
    )