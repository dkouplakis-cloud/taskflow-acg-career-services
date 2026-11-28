
"""
Custom user administration views for TaskFlow.

Provide secure, administrator-only account management
using Django's authentication system and UserProfile roles.
"""

from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import Http404
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
    AdminUserEditForm,
    AdminUserRoleForm,
    AdminUserWorkspaceForm,
    UserDirectoryFilterForm,
)
from .account_identity import (
    AccountIdentityBusyError,
    account_identity_transaction,
)
from .user_role_services import (
    change_user_role,
    get_assignable_roles,
)
from .user_workspace_services import (
    NO_WORKSPACE_ACCESS,
    WorkspaceStateChangedError,
    can_manage_workspace_membership,
    change_workspace_membership,
    create_workspace_state_token,
    get_workspace_authorization_state,
)


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

    # Evaluate editing permissions using the same
    # authorization policy as the editing endpoint.
    administrator = _get_active_administrator(request)

    can_edit_account = (
        _account_edit_denial_reason(
            administrator,
            account
        ) is None
    )

    # Determine whether the administrator is authorized
    # to manage the target account's application role.
    can_manage_role = bool(
        get_assignable_roles(
            administrator,
            account
        )
    )

        # Workspace membership management requires
    # explicit superuser and application authorization.
    can_manage_workspace = (
        can_manage_workspace_membership(
            administrator,
            account
        )
    )

    context = {
        "page_title": "User Details",
        "account": account,
        "can_edit_account": can_edit_account,
        "can_manage_role": can_manage_role,
        "can_manage_workspace": can_manage_workspace,
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

        except AccountIdentityBusyError:

            # The protected transaction has been rolled back.
            # Allow the administrator to retry safely.
            messages.error(
                request,
                "Account creation is temporarily unavailable. "
                "Please try again in a moment."
            )

            return redirect("user_management:user_create")

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


def _get_active_administrator(request):
    """
    Retrieve the requesting administrator using
    current database authorization information.
    """

    User = get_user_model()

    administrator = User.objects.filter(
        pk=request.user.pk,
        is_active=True,
        profile__role=UserProfile.Role.ADMIN
    ).first()

    if administrator is None:

        raise PermissionDenied(
            "An active administrator account is required."
        )

    return administrator

def _account_edit_denial_reason(administrator, account):
    """
    Centralize account editing authorization.

    Return a denial reason when the administrator
    cannot modify the target account, otherwise None.

    Both interface visibility and backend authorization
    must use this same policy.
    """

    profile = getattr(account, "profile", None)

    # Protect accounts with elevated Django privileges.
    if not administrator.is_superuser:

        if account.is_staff or account.is_superuser:

            return (
                "You cannot modify a protected Django account."
            )

        # Protect other application administrator identities.
        if (
            account.pk != administrator.pk
            and profile is not None
            and profile.role == UserProfile.Role.ADMIN
        ):

            return (
                "You cannot modify another administrator account."
            )

    return None

def _get_editable_account(request, pk):
    """
    Retrieve an account that the requesting
    administrator is authorized to modify.
    """

    administrator = _get_active_administrator(request)

    User = get_user_model()

    # Retrieve the current target account information.
    account = get_object_or_404(
        User.objects.select_related("profile"),
        pk=pk
    )

    # Enforce the shared account editing policy.
    denial_reason = _account_edit_denial_reason(
        administrator,
        account
    )

    if denial_reason is not None:

        raise PermissionDenied(denial_reason)

    return account

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "HEAD", "POST"])
def user_edit(request, pk):
    """
    Allow authorized administrators to modify existing
    account identity information securely.

    Credential changes, application roles and workspace
    memberships are handled through separate operations.
    """

    # Reject inactive administrator accounts.
    if not request.user.is_active:

        raise PermissionDenied(
            "An active administrator account is required."
        )

    if request.method == "POST":

        account_updated = False

        try:

            # Acquire the shared synchronization lock
            # before retrieving or validating the account.
            with account_identity_transaction():

                account = _get_editable_account(
                    request,
                    pk
                )

                form = AdminUserEditForm(
                    request.POST,
                    instance=account
                )

                if form.is_valid():

                    # Prepare the validated account without
                    # performing an unrestricted model save.
                    account = form.save(commit=False)

                    # Persist only explicitly permitted fields.
                    account.save(
                        update_fields=[
                            "username",
                            "first_name",
                            "last_name",
                            "email",
                        ]
                    )

                    account_updated = True

        except AccountIdentityBusyError:

            # The protected transaction has rolled back.
            messages.error(
                request,
                "Account editing is temporarily unavailable. "
                "Please try again in a moment."
            )

            return redirect(
                "user_management:user_edit",
                pk=pk
            )

        except IntegrityError:

            # Handle database conflicts without exposing
            # internal database implementation details.
            messages.error(
                request,
                "The account could not be updated because "
                "of a database conflict. Please review "
                "the account information and try again."
            )

            return redirect(
                "user_management:user_edit",
                pk=pk
            )

        else:

            # Report success only after the transaction
            # completes without an exception.
            if account_updated:

                messages.success(
                    request,
                    f"User '{account.username}' "
                    "was updated successfully."
                )

                return redirect(
                    "user_management:user_detail",
                    pk=account.pk
                )

    else:

        # Display the existing account information.
        account = _get_editable_account(
            request,
            pk
        )

        form = AdminUserEditForm(
            instance=account
        )

    context = {
        "page_title": "Edit User",
        "account": account,
        "form": form,
        "is_current_account": (
            account.pk == request.user.pk
        ),
    }

    return render(
        request,
        "user_management/user_edit.html",
        context
    )

@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "HEAD", "POST"])
def user_role_edit(request, pk):
    """
    Allow authorized administrators to manage
    an existing account's application role.

    Role changes are delegated exclusively to the
    transactional role management service.
    """

    # Retrieve current administrator authorization.
    administrator = _get_active_administrator(request)

    User = get_user_model()

    # Retrieve the target account and its current role.
    account = get_object_or_404(
        User.objects
        .select_related("profile")
        .prefetch_related("groups"),
        pk=pk
    )

    # Prevent unauthorized access to role management,
    # including direct requests to the endpoint.
    assignable_roles = get_assignable_roles(
        administrator,
        account
    )

    if not assignable_roles:

        raise PermissionDenied(
            "You cannot modify this account's application role."
        )

    if request.method == "POST":

        # Restrict submitted choices according to the
        # administrator's current assignment authority.
        form = AdminUserRoleForm(
            request.POST,
            administrator=administrator,
            account=account
        )

        if form.is_valid():

            try:

                # The service acquires the shared lock,
                # reloads authorization information and
                # independently validates the role change.
                updated_account = change_user_role(
                    administrator=administrator,
                    account_id=account.pk,
                    new_role=form.cleaned_data["role"]
                )

            except AccountIdentityBusyError:

                # Allow a safe manual retry when the
                # database is temporarily unavailable.
                messages.error(
                    request,
                    "Role management is temporarily "
                    "unavailable. Please try again in a moment."
                )

                return redirect(
                    "user_management:user_role_edit",
                    pk=pk
                )

            except User.DoesNotExist:

                # Handle accounts removed between
                # initial retrieval and transaction execution.
                raise Http404(
                    "The requested account no longer exists."
                )

            except ValidationError as exc:

                # Display application-level validation
                # errors without committing invalid changes.
                form.add_error(None, exc)

            except IntegrityError:

                # Avoid exposing internal database details.
                messages.error(
                    request,
                    "The application role could not be "
                    "updated because of a database conflict."
                )

                return redirect(
                    "user_management:user_role_edit",
                    pk=pk
                )

            else:

                # Report success only after the
                # transactional service has completed.
                messages.success(
                    request,
                    f"Application role for "
                    f"'{updated_account.username}' "
                    f"is now "
                    f"{updated_account.profile.get_role_display()}."
                )

                return redirect(
                    "user_management:user_detail",
                    pk=updated_account.pk
                )

    else:

        # Display the current role and authorized choices.
        form = AdminUserRoleForm(
            administrator=administrator,
            account=account
        )

    context = {
        "page_title": "Manage Application Role",
        "account": account,
        "form": form,
        "assignable_roles": assignable_roles,
        "can_assign_administrator": (
            UserProfile.Role.ADMIN in assignable_roles
        ),
    }

    return render(
        request,
        "user_management/user_role_edit.html",
        context
    )


@role_required(UserProfile.Role.ADMIN)
@require_http_methods(["GET", "HEAD", "POST"])
def user_workspace_edit(request, pk):
    """
    Manage an account's explicit Career Services
    workspace membership.

    Membership changes are delegated exclusively
    to the transactional workspace management service.
    """

    # Retrieve current administrator authorization.
    administrator = _get_active_administrator(request)

    User = get_user_model()

    # Retrieve the target account and its existing
    # application role and group memberships.
    account = get_object_or_404(
        User.objects
        .select_related("profile")
        .prefetch_related("groups"),
        pk=pk
    )

    # Require explicit workspace management authority,
    # including protection against self-assignment.
    if not can_manage_workspace_membership(
        administrator,
        account
    ):

        raise PermissionDenied(
            "You are not authorized to manage "
            "this account's workspace membership."
        )

    # Capture the state presented to the administrator.
    authorization_state = (
        get_workspace_authorization_state(account)
    )

    if request.method == "POST":

        # Validate the selected membership, signed state
        # token and mandatory confirmation.
        form = AdminUserWorkspaceForm(
            request.POST,
            administrator=administrator,
            account=account
        )

        if form.is_valid():

            try:

                # Independently recheck authorization
                # and the reviewed state inside the
                # transactional management service.
                updated_account = (
                    change_workspace_membership(
                        administrator=administrator,
                        account_id=account.pk,
                        membership=form.cleaned_data[
                            "membership"
                        ],
                        expected_state_token=form.cleaned_data[
                            "state_token"
                        ]
                    )
                )

            except AccountIdentityBusyError:

                # Handle temporary database contention
                # without exposing internal details.
                messages.error(
                    request,
                    "Workspace management is temporarily "
                    "unavailable. Please try again in a moment."
                )

                return redirect(
                    "user_management:user_workspace_edit",
                    pk=pk
                )

            except User.DoesNotExist as exc:

                # Handle accounts removed after
                # initial retrieval.
                raise Http404(
                    "The requested account no longer exists."
                ) from exc

            except WorkspaceStateChangedError as exc:

                # Discard outdated or invalid submissions.
                # Require a fresh authorization review.
                messages.warning(
                    request,
                    exc.messages[0]
                )

                return redirect(
                    "user_management:user_workspace_edit",
                    pk=pk
                )

            except ValidationError as exc:

                # Preserve the bound form and display
                # validation errors to the administrator.
                form.add_error(None, exc)

            except IntegrityError:

                # The enclosing transaction reverses
                # membership and project grant changes.
                messages.error(
                    request,
                    "Workspace access could not be updated "
                    "because of a database conflict."
                )

                return redirect(
                    "user_management:user_workspace_edit",
                    pk=pk
                )

            else:

                # Report success only after completion
                # of the transactional management service.
                selected_membership = (
                    form.cleaned_data["membership"]
                )

                membership_label = (
                    "No workspace access"
                    if selected_membership == NO_WORKSPACE_ACCESS
                    else selected_membership
                )

                messages.success(
                    request,
                    f"Workspace membership for "
                    f"'{updated_account.username}' "
                    f"is now: {membership_label}."
                )

                return redirect(
                    "user_management:user_detail",
                    pk=updated_account.pk
                )

    else:

        # Generate the signed authorization snapshot
        # for GET and HEAD requests.
        state_token = create_workspace_state_token(
            administrator=administrator,
            account=account,
            state=authorization_state
        )

        # Initialize the hidden field with the state
        # originally presented to the administrator.
        form = AdminUserWorkspaceForm(
            administrator=administrator,
            account=account,
            initial={
                "state_token": state_token
            }
        )

    # Display the same authorization snapshot
    # used to generate the signed state token.
    current_memberships = (
        authorization_state["memberships"]
    )

    project_grant_count = len(
        authorization_state["project_grants"]
    )

    context = {
        "page_title": "Manage Workspace Access",
        "account": account,
        "form": form,
        "current_memberships": current_memberships,
        "project_grant_count": project_grant_count,
        "has_multiple_memberships": (
            len(current_memberships) > 1
        ),
    }

    return render(
        request,
        "user_management/user_workspace_edit.html",
        context
    )