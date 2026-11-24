
"""
User-facing catalogue views for TaskFlow.

These views display career workshops, events,
and professional development services.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import CatalogItem


def catalog_list(request):
    """
    Display active, available catalogue items
    belonging to active categories.
    """

    # Read the search query safely.
    # Limit unusually long input to 100 characters.
    search_query = (
        request.GET.get("q") or ""
    ).strip()[:100]

    items = (
        CatalogItem.objects
        .filter(
            is_active=True,
            is_available=True,
            category__is_active=True,
        )
        .select_related("category")
        .order_by("name", "pk")
    )

    # Search service names and descriptions.
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    paginator = Paginator(items, 9)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Explore Career Services",
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "total_items": paginator.count,
        "search_query": search_query,
    }

    return render(
        request,
        "catalog/catalog_list.html",
        context
    )