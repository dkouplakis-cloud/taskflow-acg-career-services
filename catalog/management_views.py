
"""
Custom catalogue management views for TaskFlow.

These views provide the application's own
administration interface, separate from
Django's built-in admin site.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import render

from core.models import UserProfile
from core.permissions import role_required

from .models import Category, CatalogItem


@role_required(UserProfile.Role.ADMIN)
def management_dashboard(request):
    """
    Display the Administrator-only catalogue dashboard.

    Statistics are calculated directly from the database.
    """

    # Count all catalogue items.
    total_items = CatalogItem.objects.count()

    # Count items that are active and available.
    available_items = CatalogItem.objects.filter(
        is_active=True,
        is_available=True
    ).count()

    # Count catalogue categories and subcategories.
    total_categories = Category.objects.count()

    # Count registered user accounts.
    User = get_user_model()
    total_users = User.objects.count()

    # Retrieve the six most recently created items.
    recent_items = (
        CatalogItem.objects
        .select_related("category")
        .order_by("-created_at", "-pk")[:6]
    )

    context = {
        "page_title": "Catalogue Management",
        "total_items": total_items,
        "available_items": available_items,
        "total_categories": total_categories,
        "total_users": total_users,
        "recent_items": recent_items,
    }

    return render(
        request,
        "catalog/management/dashboard.html",
        context
    )