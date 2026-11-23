
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