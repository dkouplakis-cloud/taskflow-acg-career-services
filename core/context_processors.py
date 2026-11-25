
"""
Template context processors for TaskFlow.

Provide role-aware navigation permissions without
duplicating authorization logic in templates.
"""

from .permissions import (
    can_access_workspace,
    is_career_services_staff,
)


def workspace_navigation(request):
    """
    Expose Career Services workspace permissions
    to templates rendered with a request context.

    These values control navigation visibility.
    Django views must still enforce authorization.
    """
    user = request.user

    return {
        "can_access_workspace": can_access_workspace(user),
        "can_manage_projects": is_career_services_staff(user),
    }