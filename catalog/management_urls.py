
"""
URL configuration for TaskFlow's custom
catalogue administration interface.

These routes are separate from the public
catalogue and Django's built-in admin site.
"""

from django.urls import path

from .management_views import management_dashboard


app_name = "catalog_management"

urlpatterns = [
    path(
        "",
        management_dashboard,
        name="dashboard"
    ),
]