
"""
URL configuration for TaskFlow's
user-facing career services catalogue.

These routes are separate from the
custom Administrator catalogue interface.
"""

from django.urls import path

from .views import catalog_list


app_name = "catalog"

urlpatterns = [
    path(
        "",
        catalog_list,
        name="list"
    ),
]