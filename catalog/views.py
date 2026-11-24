
"""
User-facing catalogue views for TaskFlow.

These views display career workshops, events,
and professional development services.
"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import CatalogItem, Category


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


    # Read the selected catalogue category.
    selected_category = (
        request.GET.get("category") or ""
    ).strip()[:120]

    # Only active categories should be offered.
    categories = (
        Category.objects
        .filter(is_active=True)
        .order_by("name", "pk")
    )

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
    
    # Filter catalogue items by category slug.
    # This can be combined with the text search.
    if selected_category:
        items = items.filter(
            category__slug=selected_category
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
        "categories": categories,
        "selected_category": selected_category,
    }

    return render(
        request,
        "catalog/catalog_list.html",
        context
    )

def catalog_detail(request, slug):
    """
    Display the complete details of a career service.

    Only active and available services belonging
    to active categories may be accessed.
    """

    item = get_object_or_404(
        CatalogItem.objects.select_related("category"),
        slug=slug,
        is_active=True,
        is_available=True,
        category__is_active=True
    )

    context = {
        "page_title": item.name,
        "item": item,
    }

    return render(
        request,
        "catalog/catalog_detail.html",
        context
    )