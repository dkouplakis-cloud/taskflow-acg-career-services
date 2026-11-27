"""
URL configuration for student registration management.

Keep administrator registration-review routes
separate from public authentication routes.
"""

from django.urls import path

from .registration_management_views import (
    registration_request_approve,
    registration_request_detail,
    registration_request_list,
    registration_request_reject,
)

app_name = "registration_management"

urlpatterns = [
    # Administrator-only list of pending applications.
    path(
        "",
        registration_request_list,
        name="request_list",
    ),

    # Display an application for administrator review.
    # This GET endpoint never changes registration status.
    path(
        "<int:pk>/review/",
        registration_request_detail,
        name="request_detail",
    ),

    # Approval is restricted to authenticated
    # administrators and HTTP POST requests.
    path(
        "<int:pk>/approve/",
        registration_request_approve,
        name="request_approve",
    ),

    # Only administrators may reject applications.
    # Rejection requires an HTTP POST request.
    path(
        "<int:pk>/reject/",
        registration_request_reject,
        name="request_reject",
    ),
]