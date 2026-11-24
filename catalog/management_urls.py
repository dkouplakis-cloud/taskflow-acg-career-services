
"""
URL configuration for TaskFlow's custom
catalogue administration interface.

These routes are separate from the public
catalogue and Django's built-in admin site.
"""

from django.urls import path
from .management_views import (
    catalog_item_create,
    catalog_item_delete,
    catalog_item_edit,
    catalog_item_list,
    category_create,
    category_delete,
    category_edit,
    category_list,
)
from .management_views import management_dashboard


app_name = "catalog_management"

urlpatterns = [
    path(
        "",
        management_dashboard,
        name="dashboard"
    ),

    path("categories/", category_list, name="category_list"),
    path("categories/new/", category_create, name="category_create"),
    
    path(
    "categories/<int:pk>/edit/",
    category_edit,
    name="category_edit"
    ),
    
    path(
    "categories/<int:pk>/delete/",
    category_delete,
    name="category_delete"
    ),
    
    path(
    "items/",
    catalog_item_list,
    name="item_list"
    ),
    
    # Catalogue item management.
    path(
    "items/new/",
    catalog_item_create,
    name="item_create"
    ),
    
    path(
    "items/<int:pk>/edit/",
    catalog_item_edit,
    name="item_edit"
    ),

    path(
        "items/<int:pk>/delete/",
        catalog_item_delete,
        name="item_delete"
    ),

]