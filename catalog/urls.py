
"""
URL configuration for TaskFlow's
user-facing Career Services catalogue.

These routes are separate from the
custom Administrator catalogue interface.
"""

from django.urls import path

from .cart_views import add_to_cart, cart_detail
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

    # Add an available service to the cart.
    path(
        "<slug:slug>/add-to-cart/",
        add_to_cart,
        name="add_to_cart"
    ),

    # View an individual career service.
    path(
        "<slug:slug>/",
        catalog_detail,
        name="detail"
    ),
]