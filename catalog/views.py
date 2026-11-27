
"""
User-facing catalogue views for TaskFlow.

These views display career workshops, events,
and professional development services.
"""

from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_not_required
from .forms import CatalogFilterForm
from .models import CatalogItem, Category
from .visibility import (
    get_visible_category_ids,
    get_visible_subtree_ids,
)

# Allow anonymous visitors to browse and search public career services.
@login_not_required
def catalog_list(request):
    """
    Display active, available catalogue items
    belonging to completely active category hierarchies.
    """

    # Read the search query safely.
    # Limit unusually long input to 100 characters.
    search_query = (
        request.GET.get("q") or ""
    ).strip()[:100]

    # Bind advanced filters to the submitted GET parameters.
    # Validate all values before using them in database queries.
    filter_form = CatalogFilterForm(request.GET)

    # Read the selected catalogue category.
    selected_category = (
        request.GET.get("category") or ""
    ).strip()[:120]

    # Only categories with a completely active hierarchy
    # should be available to catalogue visitors.
    visible_category_ids = get_visible_category_ids()

    categories = (
        Category.objects
        .filter(pk__in=visible_category_ids)
        .order_by("name", "pk")
    )

    # Exclude services belonging to inactive category hierarchies.
    items = (
        CatalogItem.objects
        .filter(
            is_active=True,
            is_available=True,
            category_id__in=visible_category_ids,
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

    # Include the selected category and all of its
    # visible descendants when filtering services.
    if selected_category:
        subtree_ids = get_visible_subtree_ids(
            categories,
            selected_category
        )

        items = items.filter(
            category_id__in=subtree_ids
        )

    # Apply advanced filters only after server-side validation.
    if filter_form.is_valid():

        min_price = filter_form.cleaned_data["min_price"]
        max_price = filter_form.cleaned_data["max_price"]
        delivery_format = filter_form.cleaned_data["delivery_format"]

        # Include zero as a valid price boundary.
        if min_price is not None:
            items = items.filter(price__gte=min_price)

        if max_price is not None:
            items = items.filter(price__lte=max_price)

        # Restrict results to the selected delivery format.
        if delivery_format:
            items = items.filter(
                delivery_format=delivery_format
            )

    else:
        # Invalid filters must not silently broaden the results.
        # The template will display the corresponding errors.
        items = items.none()


    # Preserve validated search and filter parameters
    # when visitors navigate between catalogue pages.
    pagination_params = {}

    if search_query:
        pagination_params["q"] = search_query

    if selected_category:
        pagination_params["category"] = selected_category

    if filter_form.is_valid():

        for field_name in (
            "min_price",
            "max_price",
            "delivery_format",
        ):
            value = filter_form.cleaned_data[field_name]

            # Preserve zero-price filters while excluding
            # empty or unspecified filter values.
            if value is not None and value != "":
                pagination_params[field_name] = str(value)

    # Encode filter values safely for pagination URLs.
    pagination_query = urlencode(pagination_params)

    # Paginate only after applying every requested filter.
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
        "pagination_query": pagination_query,
        "filter_form": filter_form,
    }

    return render(
        request,
        "catalog/catalog_list.html",
        context
    )

# Allow anonymous visitors to view available career service details.
@login_not_required
def catalog_detail(request, slug):
    """
    Display the complete details of a career service.

    Only active and available services belonging to
    completely active category hierarchies may be accessed.
    """

    # Prevent direct URL access to services belonging
    # to an inactive category hierarchy.
    item = get_object_or_404(
        CatalogItem.objects.select_related("category"),
        slug=slug,
        is_active=True,
        is_available=True,
        category_id__in=get_visible_category_ids()
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