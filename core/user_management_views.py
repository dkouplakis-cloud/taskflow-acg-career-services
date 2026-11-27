
"""
Custom user administration views for TaskFlow.

Provide secure, administrator-only account management
using Django's authentication system and UserProfile roles.
"""

from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import (
    require_safe,
    require_http_methods,
)
from django.contrib import messages
from django.db import IntegrityError
from .models import UserProfile
from .permissions import role_required
from .user_management_forms import (
    AdminUserCreationForm,
    UserDirectoryFilterForm,
)
from .account_identity import account_identity_transaction


@role_required(UserProfile.Role.ADMIN)
@require_safe
def user_list(request):
    """
    Display registered accounts in the custom
    administration workspace.

    Support validated account searches, role filtering,
    account status filtering and pagination.
    """

    # Reject inactive administrator accounts.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    User = get_user_model()

    # Retrieve profiles and group memberships efficiently.
    users = (
        User.objects
        .select_related("profile")
        .prefetch_related("groups")
        .order_by("username", "pk")
    )

    # Preserve the total account count before filtering.
    registered_users_count = users.count()

    # Validate submitted directory filters.
    filter_form = UserDirectoryFilterForm(request.GET)

    pagination_params = {}

    if filter_form.is_valid():

        search_query = filter_form.cleaned_data["q"]
        selected_role = filter_form.cleaned_data["role"]
        selected_status = filter_form.cleaned_data["status"]

        # Search account names, usernames and email addresses.
        if search_query:

            users = users.annotate(
                full_name=Concat(
                    "first_name",
                    Value(" "),
                    "last_name"
                )
            ).filter(
                Q(username__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(full_name__icontains=search_query)
                | Q(email__icontains=search_query)
            )

            pagination_params["q"] = search_query

        # Restrict results to the selected application role.
        if selected_role:

            users = users.filter(
                profile__role=selected_role
            )

            pagination_params["role"] = selected_role

        # Filter accounts according to activation status.
        if selected_status:

            users = users.filter(
                is_active=(selected_status == "active")
            )

            pagination_params["status"] = selected_status

    else:

        # Invalid filters must not silently broaden results.
        users = users.none()

    # Preserve validated parameters across directory pages.
    pagination_query = urlencode(pagination_params)

    # Keep large account directories manageable.
    paginator = Paginator(users, 10)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Manage Users",
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "total_users": paginator.count,
        "registered_users_count": registered_users_count,
        "filter_form": filter_form,
        "pagination_query": pagination_query,
    }

    return render(
        request,
        "user_management/user_list.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_safe
def user_detail(request, pk):
    """
    Display individual account information within
    the custom user administration interface.

    Access is restricted to active administrators,
    independently of their workspace membership.
    """

    # Reject inactive administrator accounts.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    User = get_user_model()

    # Retrieve the requested account and its related
    # profile and group memberships efficiently.
    account = get_object_or_404(
        User.objects
        .select_related("profile")
        .prefetch_related("groups"),
        pk=pk
    )

    context = {
        "page_title": "User Details",
        "account": account,
        "is_current_account": (
            account.pk == request.user.pk
        ),
    }

    return render(
        request,
        "user_management/user_detail.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "HEAD", "POST"])
def user_create(request):
    """
    Allow authorized administrators to create
    registered TaskFlow accounts securely.

    New accounts receive the Regular User role
    through the existing profile creation signal.
    """

    # Reject inactive administrator accounts.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    if request.method == "POST":

        # Bind submitted account information for validation.
        form = AdminUserCreationForm(request.POST)

        try:

            # Serialize account identity validation and creation
            # with all participating registration operations.
            with account_identity_transaction():

                if form.is_valid():

                    # Django securely hashes the password
                    # through the inherited form save method.
                    account = form.save()

                else:

                    account = None

        except IntegrityError:

            # Roll back unsuccessful account creation
            # without exposing database error details.
            form.add_error(
                None,
                "The account could not be created. "
                "Check that the username and email "
                "address are still available."
            )

            account = None

        if account is not None:

            messages.success(
                request,
                f"User '{account.username}' "
                "was created successfully."
            )

            # Redirect after successful submission to
            # prevent accidental duplicate form submissions.
            return redirect(
                "user_management:user_detail",
                pk=account.pk
            )

    else:

        # Display an empty account creation form.
        form = AdminUserCreationForm()

    context = {
        "page_title": "Create User",
        "form": form,
    }

    return render(
        request,
        "user_management/user_form.html",
        context
    )