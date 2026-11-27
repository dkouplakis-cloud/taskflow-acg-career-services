
"""
URL configuration for TaskFlow's custom
user administration interface.

These routes are separate from public account
registration and Django's built-in administration.
"""

from django.urls import path

from .user_management_views import (
    user_list,
    user_detail,
    user_create,
)


# Dedicated namespace for custom user administration.
app_name = "user_management"


urlpatterns = [
    # Administrator-only registered account directory.
    path(
        "",
        user_list,
        name="user_list"
    ),

    # Secure administrator-controlled account creation.
    path(
        "create/",
        user_create,
        name="user_create"
    ),

    # Administrator-only individual account details.
    path(
        "<int:pk>/",
        user_detail,
        name="user_detail"
    ),
]