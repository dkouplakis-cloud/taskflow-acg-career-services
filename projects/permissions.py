
"""
Project-level authorization helpers for TaskFlow.

Career Services staff have office-wide project visibility.
Authorized faculty and student assistants can access
only projects explicitly assigned to their accounts.
"""


from core.permissions import is_career_services_staff

from .models import Project


SCOPED_PROJECT_GROUP_NAMES = (
    "Authorized Faculty",
    "Career Services Student Assistants",
)


def visible_projects_for_user(user):
    """
    Return projects the specified user may view.

    Career Services staff: all projects.
    Authorized faculty/assistants: explicitly granted projects.
    Everyone else: no internal projects.
    """

    # Deny access to anonymous or inactive accounts.
    if not user.is_authenticated or not user.is_active:
        return Project.objects.none()

    # Career Services staff have office-wide visibility.
    if is_career_services_staff(user):
        return Project.objects.all()

    # Other users must belong to an authorized scoped group.
    is_scoped_member = user.groups.filter(
        name__in=SCOPED_PROJECT_GROUP_NAMES
    ).exists()

    if not is_scoped_member:
        return Project.objects.none()

    # Only projects with an explicit ProjectAccess grant.
    return Project.objects.filter(
        access_grants__user=user
    ).distinct()

def can_modify_project_tasks(user, project):
    """
    Check whether a user may create or modify tasks
    within the specified Career Services project.

    Career Services staff may manage all tasks.
    Other authorized workspace members require
    an explicit Contributor-level project grant.
    """

    # Deny anonymous and inactive accounts.
    if not user.is_authenticated or not user.is_active:
        return False

    # Staff have office-wide task management permissions.
    if is_career_services_staff(user):
        return True

    # Faculty and student assistants must belong
    # to an explicitly authorized workspace group.
    is_scoped_member = user.groups.filter(
        name__in=SCOPED_PROJECT_GROUP_NAMES
    ).exists()

    if not is_scoped_member:
        return False

    # Only Contributor grants allow task modifications.
    return project.access_grants.filter(
        user=user,
        access_level="contributor"
    ).exists()