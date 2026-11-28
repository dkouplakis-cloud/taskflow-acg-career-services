
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
    user_edit,
    user_role_edit,
    user_workspace_edit,
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

    # Individual account information.
    path(
        "<int:pk>/",
        user_detail,
        name="user_detail"
    ),

    # Secure modification of existing account identities.
    path(
        "<int:pk>/edit/",
        user_edit,
        name="user_edit"
    ),

        # Secure application role management.
    path(
        "<int:pk>/role/",
        user_role_edit,
        name="user_role_edit"
    ),

        # Secure Career Services workspace membership management.
    path(
        "<int:pk>/workspace/",
        user_workspace_edit,
        name="user_workspace_edit"
    ),
]