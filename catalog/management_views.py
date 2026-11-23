
"""
Custom catalogue management views for TaskFlow.

These views provide the application's own
administration interface, separate from
Django's built-in admin site.
"""

from django.shortcuts import render

from core.models import UserProfile
from core.permissions import role_required


@role_required(UserProfile.Role.ADMIN)
def management_dashboard(request):
    """
    Display the custom catalogue management dashboard.

    Only users with the Administrator profile role
    may access this view.
    """

    context = {
        "page_title": "Catalogue Management",
    }

    return render(
        request,
        "catalog/management/dashboard.html",
        context
    )