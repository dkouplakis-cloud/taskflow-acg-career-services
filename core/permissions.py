
"""
Reusable role-based authorization for TaskFlow.

Restrict access to views based on the authenticated
user's UserProfile role.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import UserProfile


def role_required(*allowed_roles):
    """
    Restrict a view to users with an allowed role.

    Anonymous users are redirected to login.
    Authenticated users without permission receive 403.

    Example:
        @role_required(UserProfile.Role.ADMIN)
    """

    if not allowed_roles:
        raise ValueError(
            "role_required requires at least one allowed role."
        )

    def decorator(view_func):

        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):

            has_permission = UserProfile.objects.filter(
                user=request.user,
                role__in=allowed_roles
            ).exists()

            if not has_permission:
                raise PermissionDenied(
                    "You do not have permission "
                    "to access this page."
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator

# ==========================================================
# CAREER SERVICES WORKSPACE AUTHORIZATION
# ==========================================================

WORKSPACE_GROUP_NAMES = (
    "Career Services Staff",
    "Authorized Faculty",
    "Career Services Student Assistants",
)

def is_career_services_staff(user):
    """
    Check whether a user has organization-wide
    Career Services staff authorization.

    Superuser status alone does not grant access.
    """

    return (
        user.is_authenticated
        and user.is_active
        and user.groups.filter(
            name="Career Services Staff"
        ).exists()
    )

def workspace_required(view_func):
    """
    Restrict internal Career Services functionality
    to explicitly authorized personnel.

    Anonymous users are redirected to login.
    Authenticated users without authorization receive 403.

    Project-specific permissions must be checked
    separately inside the protected view.
    """

    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):

        # An inactive account must not access
        # confidential office functionality.
        if not request.user.is_active:
            raise PermissionDenied(
                "Your account is not active."
            )

        # Access is granted only through explicit
        # Career Services group membership.
        is_authorized = request.user.groups.filter(
            name__in=WORKSPACE_GROUP_NAMES
        ).exists()

        if not is_authorized:
            raise PermissionDenied(
                "You are not authorized to access "
                "the Career Services workspace."
            )

        return view_func(request, *args, **kwargs)

    return wrapped_view

def career_services_staff_required(view_func):
    """
    Restrict office-wide management operations to
    explicitly authorized Career Services staff.

    Anonymous users are redirected to login.
    Other users receive HTTP 403 Forbidden.
    """

    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):

        # Superuser status alone does not grant
        # Career Services staff authorization.
        if not is_career_services_staff(request.user):
            raise PermissionDenied(
                "Career Services staff authorization is required."
            )

        return view_func(request, *args, **kwargs)

    return wrapped_view