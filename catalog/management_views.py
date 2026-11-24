
"""
Custom catalogue management views for TaskFlow.

These views provide the application's own
administration interface, separate from
Django's built-in admin site.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render

from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from .forms import CategoryForm, CatalogItemForm
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.deletion import ProtectedError
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

@role_required(UserProfile.Role.ADMIN)
def category_list(request):
    """
    Display catalogue categories and subcategories
    in the custom Administrator workspace.

    Use pagination to keep the interface manageable.
    """

    categories = (
        Category.objects
        .select_related("parent")
        .annotate(
            item_count=Count(
                "items",
                distinct=True
            ),
            subcategory_count=Count(
                "subcategories",
                distinct=True
            )
        )
        .order_by("name", "pk")
    )

    paginator = Paginator(categories, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Manage Categories",
        "page_obj": page_obj,
        "categories": page_obj.object_list,
        "total_categories": paginator.count,
    }

    return render(
        request,
        "catalog/management/category_list.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def category_create(request):
    """
    Allow administrators to create catalogue categories
    and subcategories using the validated CategoryForm.
    """

    form = CategoryForm(
        request.POST if request.method == "POST" else None
    )

    if request.method == "POST" and form.is_valid():
        category = form.save()

        messages.success(
            request,
            f'Category "{category.name}" created successfully.'
        )

        return redirect("catalog_management:category_list")

    context = {
        "page_title": "Create Category",
        "form": form,
    }

    return render(
        request,
        "catalog/management/category_form.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def category_edit(request, pk):
    """
    Allow administrators to edit an existing
    catalogue category or subcategory.

    Reuse CategoryForm to preserve validation,
    category hierarchy, and stable slugs.
    """

    # Retrieve the category or return HTTP 404.
    category = get_object_or_404(Category, pk=pk)

    # Bind the form to the existing category.
    form = CategoryForm(
        request.POST if request.method == "POST" else None,
        instance=category
    )

    # Validate and save submitted changes.
    if request.method == "POST" and form.is_valid():
        category = form.save()

        messages.success(
            request,
            f'Category "{category.name}" updated successfully.'
        )

        return redirect("catalog_management:category_list")

    # Reuse the shared category form template.
    context = {
        "page_title": "Edit Category",
        "form": form,
        "is_edit": True,
        "category": category,
    }

    return render(
        request,
        "catalog/management/category_form.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def category_delete(request, pk):
    """
    Allow administrators to delete a category
    only after confirmation.

    Protect categories containing catalogue
    items or subcategories.
    """

    category = get_object_or_404(Category, pk=pk)

    # Check for dependent records.
    item_count = category.items.count()
    subcategory_count = category.subcategories.count()

    can_delete = (
        item_count == 0
        and subcategory_count == 0
    )

    if request.method == "POST":

        # Do not delete categories with dependencies.
        if not can_delete:
            messages.error(
                request,
                "This category cannot be deleted because "
                "it contains catalogue items or subcategories."
            )

            return redirect(
                "catalog_management:category_list"
            )

        category_name = category.name

        try:
            category.delete()

        except ProtectedError:
            # Handle protected relationships safely,
            # including those added concurrently.
            messages.error(
                request,
                "This category cannot be deleted because "
                "other records depend on it."
            )

            return redirect(
                "catalog_management:category_list"
            )

        messages.success(
            request,
            f'Category "{category_name}" deleted successfully.'
        )

        return redirect(
            "catalog_management:category_list"
        )

    # GET displays the confirmation page only.
    context = {
        "page_title": "Delete Category",
        "category": category,
        "item_count": item_count,
        "subcategory_count": subcategory_count,
        "can_delete": can_delete,
    }

    return render(
        request,
        "catalog/management/category_confirm_delete.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def catalog_item_create(request):
    """
    Allow administrators to create catalogue items.

    Validate submitted information and uploaded
    images using CatalogItemForm.
    """

    # Bind submitted data and uploaded files.
    form = CatalogItemForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None
    )

    # Validate the submitted form.
    if request.method == "POST" and form.is_valid():

        # Save the catalogue item to the database.
        item = form.save()

        # Notify the administrator.
        messages.success(
            request,
            f'Catalogue item "{item.name}" created successfully.'
        )

        # Return to the existing administration dashboard.
        return redirect(
            "catalog_management:dashboard"
        )

    # Display the form or its validation errors.
    context = {
        "page_title": "Create Catalogue Item",
        "form": form,
        "is_edit": False,
    }

    return render(
        request,
        "catalog/management/item_form.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET"])
def catalog_item_list(request):
    """
    Display catalogue items in the custom
    Administrator workspace.

    Retrieve related categories efficiently
    and paginate results for scalability.
    """

    # Retrieve catalogue items and their categories.
    items = (
        CatalogItem.objects
        .select_related("category")
        .order_by("name", "pk")
    )

    # Display ten catalogue items per page.
    paginator = Paginator(items, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    # Prepare data for the management template.
    context = {
        "page_title": "Manage Catalogue Items",
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "total_items": paginator.count,
    }

    return render(
        request,
        "catalog/management/item_list.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def catalog_item_edit(request, pk):
    """
    Allow administrators to edit an existing
    catalogue item through a dedicated form.

    Preserve the current image unless the
    administrator uploads a replacement.
    """

    # Retrieve the requested item or return 404.
    item = get_object_or_404(
        CatalogItem,
        pk=pk
    )

    # Load existing values and bind submitted changes.
    form = CatalogItemForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=item
    )

    # Validate and save submitted changes.
    if request.method == "POST" and form.is_valid():

        updated_item = form.save()

        messages.success(
            request,
            f'Catalogue item "{updated_item.name}" updated successfully.'
        )

        return redirect(
            "catalog_management:item_list"
        )

    # Display the existing values or validation errors.
    context = {
        "page_title": "Edit Catalogue Item",
        "form": form,
        "item": item,
        "is_edit": True,
    }

    return render(
        request,
        "catalog/management/item_form.html",
        context
    )