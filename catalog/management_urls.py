
"""
URL configuration for TaskFlow's custom
catalogue administration interface.

These routes are separate from the public
catalogue and Django's built-in admin site.
"""

from django.urls import path
from .management_views import (
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
]