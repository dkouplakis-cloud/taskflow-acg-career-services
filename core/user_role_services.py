
"""
Secure application role management for TaskFlow.

Application roles are managed independently of Django
authentication privileges and Career Services workspace
memberships.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from .account_identity import account_identity_transaction
from .models import UserProfile


def get_assignable_roles(administrator, account):
    """
    Return the application roles that an administrator
    is permitted to assign to the specified account.

    An empty tuple indicates that role modification
    is not permitted.

    This policy is shared by the service and interface.
    """

    administrator_profile = getattr(
        administrator,
        "profile",
        None
    )

    account_profile = getattr(
        account,
        "profile",
        None
    )

    # Require an active application administrator.
    if (
        not administrator.is_authenticated
        or not administrator.is_active
        or administrator_profile is None
        or administrator_profile.role != UserProfile.Role.ADMIN
    ):
        return ()

    # Accounts without a profile cannot be managed
    # safely through application role assignment.
    if account_profile is None:
        return ()

    # Prevent administrators from changing their own role.
    if administrator.pk == account.pk:
        return ()

    # Ordinary administrators cannot modify protected
    # Django accounts or other application administrators.
    if not administrator.is_superuser:

        if account.is_staff or account.is_superuser:
            return ()

        if account_profile.role == UserProfile.Role.ADMIN:
            return ()

        # Restrict ordinary administrators to assigning
        # Regular User and Power User roles.
        return (
            UserProfile.Role.REGULAR,
            UserProfile.Role.POWER,
        )

    # Django superusers who also hold the application
    # Administrator role may assign all application roles.
    return (
        UserProfile.Role.REGULAR,
        UserProfile.Role.POWER,
        UserProfile.Role.ADMIN,
    )


@account_identity_transaction()
def change_user_role(*, administrator, account_id, new_role):
    """
    Change an account's application role securely.

    Recheck current administrative authorization inside
    the shared transaction before modifying permissions.
    """

    User = get_user_model()

    if not administrator.is_authenticated:
        raise PermissionDenied(
            "Administrator authorization is required."
        )

    # Reload the acting administrator to avoid relying
    # on potentially outdated authorization information.
    current_administrator = (
        User.objects
        .select_related("profile")
        .filter(pk=administrator.pk)
        .first()
    )

    if (
        current_administrator is None
        or not current_administrator.is_active
        or getattr(
            current_administrator,
            "profile",
            None
        ) is None
        or current_administrator.profile.role
        != UserProfile.Role.ADMIN
    ):
        raise PermissionDenied(
            "An active administrator account is required."
        )

    # Retrieve the current target account inside
    # the protected transaction.
    account = (
        User.objects
        .select_related("profile")
        .get(pk=account_id)
    )

    allowed_roles = get_assignable_roles(
        current_administrator,
        account
    )

    if not allowed_roles:
        raise PermissionDenied(
            "You cannot modify this account's role."
        )

    # Reject invalid or manipulated role identifiers.
    if new_role not in UserProfile.Role.values:
        raise ValidationError(
            "Select a valid application role."
        )

    # Enforce the administrator's assignment authority.
    if new_role not in allowed_roles:
        raise PermissionDenied(
            "You are not authorized to assign this role."
        )

    profile = account.profile

    # Avoid unnecessary database updates when the
    # requested application role is already assigned.
    if profile.role == new_role:
        return account

    # Preserve at least one active application
    # administrator to prevent administrative lockout.
    if (
        account.is_active
        and profile.role == UserProfile.Role.ADMIN
        and new_role != UserProfile.Role.ADMIN
    ):

        has_other_administrator = (
            UserProfile.objects.filter(
                role=UserProfile.Role.ADMIN,
                user__is_active=True
            )
            .exclude(user_id=account.pk)
            .exists()
        )

        if not has_other_administrator:
            raise ValidationError(
                "The last active administrator "
                "cannot be demoted."
            )

    # Update only the application role and its timestamp.
    # Django privileges and group memberships remain intact.
    profile.role = new_role

    profile.save(
        update_fields=[
            "role",
            "updated_at",
        ]
    )

    return account