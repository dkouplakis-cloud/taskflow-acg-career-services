
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
from .visibility import get_visible_category_ids


@login_required
@require_POST
def add_to_cart(request, slug):
    """
    Add one available catalogue item to the
    authenticated user's session cart.
    """

    # Prevent hidden services from being added directly.
    item = get_object_or_404(
        CatalogItem,
        slug=slug,
        is_active=True,
        is_available=True,
        category_id__in=get_visible_category_ids(),
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

    Include unavailable services so users can
    identify and remove them.

    Prices are retrieved from the database.
    """

    cart = load_cart(request)

    # Retrieve categories belonging to active hierarchies.
    visible_category_ids = get_visible_category_ids()

    # Retrieve all existing cart items, including
    # services that have become unavailable.
    items = (
        CatalogItem.objects
        .filter(pk__in=cart.keys())
        .select_related("category")
        .order_by("name", "pk")
    )

    cart_lines = []
    total_amount = Decimal("0.00")
    total_quantity = 0
    has_unavailable_items = False

    # Track which cart items still exist in the database.
    existing_item_ids = set()

    for item in items:
        existing_item_ids.add(str(item.pk))
        quantity = cart[str(item.pk)]
        subtotal = item.price * quantity

        # Check service availability and its complete
        # category hierarchy before allowing checkout.
        can_checkout = (
            item.is_active
            and item.is_available
            and item.category_id in visible_category_ids
        )

        if not can_checkout:
            has_unavailable_items = True

        cart_lines.append({
            "item": item,
            "quantity": quantity,
            "subtotal": subtotal,
            "can_checkout": can_checkout,
        })

        total_amount += subtotal
        total_quantity += quantity

    # Identify session entries whose catalogue records
    # have been deleted from the database.
    missing_item_ids = [
        item_id
        for item_id in cart
        if item_id not in existing_item_ids
    ]

    if missing_item_ids:
        has_unavailable_items = True

    context = {
        "page_title": "My Cart",
        "cart_lines": cart_lines,
        "total_amount": total_amount,
        "total_quantity": total_quantity,
        "has_unavailable_items": has_unavailable_items,
        "missing_item_ids": missing_item_ids,
    }

    return render(
        request,
        "catalog/cart_detail.html",
        context
    )

@login_required
@require_POST
def update_cart_quantity(request, slug):
    """
    Update the quantity of a service already in the cart.

    Only quantities between 1 and the configured
    maximum are accepted.
    """

    # Prevent quantity updates for hidden services.
    item = get_object_or_404(
        CatalogItem,
        slug=slug,
        is_active=True,
        is_available=True,
        category_id__in=get_visible_category_ids(),
    )

    cart = load_cart(request)
    item_id = str(item.pk)

    # Only existing cart items can be updated.
    if item_id not in cart:
        messages.warning(
            request,
            "This service is not in your cart."
        )
        return redirect("catalog:cart")

    quantity_text = request.POST.get("quantity", "")

    # Accept only canonical integer values from 1 to 10.
    valid_quantities = {
        str(number)
        for number in range(1, MAX_QUANTITY_PER_ITEM + 1)
    }

    if quantity_text not in valid_quantities:
        messages.error(
            request,
            "Please choose a quantity between "
            f"1 and {MAX_QUANTITY_PER_ITEM}."
        )
        return redirect("catalog:cart")

    cart[item_id] = int(quantity_text)
    save_cart(request, cart)

    messages.success(
        request,
        f"Quantity updated for {item.name}."
    )

    return redirect("catalog:cart")

@login_required
@require_POST
def remove_from_cart(request, slug):
    """
    Remove an existing catalogue item from the
    authenticated user's session cart.

    Removal is permitted even if the service
    has become inactive or unavailable.
    """

    item = get_object_or_404(
        CatalogItem,
        slug=slug
    )

    cart = load_cart(request)
    item_id = str(item.pk)

    # Check whether the item exists in the cart.
    if item_id not in cart:
        messages.warning(
            request,
            "This service is not in your cart."
        )

        return redirect("catalog:cart")

    # Remove the selected item.
    del cart[item_id]

    # Persist the updated session.
    save_cart(request, cart)

    messages.success(
        request,
        f"{item.name} was removed from your cart."
    )

    return redirect("catalog:cart")

@login_required
@require_POST
def remove_missing_cart_item(request, item_id):
    """
    Remove a cart entry whose catalogue item
    no longer exists in the database.

    Only entries already present in the user's
    session cart can be removed.
    """

    cart = load_cart(request)
    item_key = str(item_id)

    # The item must exist in this user's cart.
    if item_key not in cart:
        messages.warning(
            request,
            "This item is no longer in your cart."
        )
        return redirect("catalog:cart")

    # This endpoint is only for deleted services.
    # Existing services use the normal removal view.
    if CatalogItem.objects.filter(pk=item_id).exists():
        messages.error(
            request,
            "This service still exists. Please use "
            "its regular Remove from cart button."
        )
        return redirect("catalog:cart")

    # Remove the missing item from the session.
    del cart[item_key]
    save_cart(request, cart)

    messages.success(
        request,
        "The deleted service was removed from your cart."
    )

    return redirect("catalog:cart")