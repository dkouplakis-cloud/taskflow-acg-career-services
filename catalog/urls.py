
"""
URL configuration for TaskFlow's
user-facing Career Services catalogue.

These routes are separate from the
custom Administrator catalogue interface.
"""

from django.urls import path

from .cart_views import (
    add_to_cart,
    cart_detail,
    remove_from_cart,
    remove_missing_cart_item,
    update_cart_quantity,
)

from .checkout_views import (
    order_confirmation,
    order_history,
    place_order,
)

from .views import catalog_detail, catalog_list


app_name = "catalog"

urlpatterns = [
    # Browse available career services.
    path(
        "",
        catalog_list,
        name="list"
    ),

    # View the authenticated user's cart.
    path(
        "cart/",
        cart_detail,
        name="cart"
    ),

    # Remove a deleted service from the session cart.
    path(
        "cart/remove-missing/<int:item_id>/",
        remove_missing_cart_item,
        name="remove_missing_cart_item"
    ),

    # Submit a simulated checkout.
    path(
        "checkout/",
        place_order,
        name="place_order"
    ),

    # Show the authenticated user's previous catalogue orders.
    path(
        "orders/",
        order_history,
        name="order_history"
    ),

    # View an order confirmation.
    path(
        "orders/<int:order_id>/confirmation/",
        order_confirmation,
        name="order_confirmation"
    ),

    # Add an available service to the cart.
    path(
        "<slug:slug>/add-to-cart/",
        add_to_cart,
        name="add_to_cart"
    ),

    # Update the quantity of a cart item.
    path(
        "<slug:slug>/update-quantity/",
        update_cart_quantity,
        name="update_cart_quantity"
    ),

    # Remove a service from the cart.
    path(
        "<slug:slug>/remove-from-cart/",
        remove_from_cart,
        name="remove_from_cart"
    ),

    # View an individual career service.
    path(
        "<slug:slug>/",
        catalog_detail,
        name="detail"
    ),
]