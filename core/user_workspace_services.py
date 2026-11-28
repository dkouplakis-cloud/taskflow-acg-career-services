
"""
Secure Career Services workspace membership management.

Workspace authorization remains independent of application
roles, Django authentication privileges and account identity.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
import hashlib
import json
from django.core import signing
from projects.models import ProjectAccess

from .account_identity import account_identity_transaction
from .models import UserProfile
from .permissions import WORKSPACE_GROUP_NAMES


# Explicit selection representing no internal workspace access.
NO_WORKSPACE_ACCESS = "none"


# Isolate workspace authorization tokens from other
# signed values used throughout the application.
WORKSPACE_STATE_SALT = "taskflow.workspace.authorization"

# Require administrators to review authorization
# again when a management form is older than 30 minutes.
WORKSPACE_STATE_MAX_AGE = 1800


class WorkspaceStateChangedError(ValidationError):
    """
    Raised when an authorization form is outdated,
    expired or contains an invalid state token.
    """

def get_workspace_authorization_state(account):
    """
    Capture the authorization state relevant to
    a workspace membership update.
    """

    project_grants = list(
        ProjectAccess.objects.filter(
            user_id=account.pk
        )
        .order_by("pk")
        .values(
            "pk",
            "project_id",
            "access_level"
        )
    )

    return {
        "is_active": account.is_active,
        "memberships": list(
            get_workspace_memberships(account)
        ),
        "project_grants": project_grants,
    }


def _workspace_state_fingerprint(state):
    """
    Produce a deterministic fingerprint of the
    account's current workspace authorization.
    """

    serialized_state = json.dumps(
        state,
        sort_keys=True,
        separators=(",", ":")
    )

    return hashlib.sha256(
        serialized_state.encode("utf-8")
    ).hexdigest()


def create_workspace_state_token(
    *,
    administrator,
    account,
    state
):
    """
    Sign the reviewed authorization state and
    bind it to the administrator and target account.
    """

    return signing.dumps(
        {
            "administrator_id": administrator.pk,
            "account_id": account.pk,
            "fingerprint": (
                _workspace_state_fingerprint(state)
            ),
        },
        salt=WORKSPACE_STATE_SALT
    )


def verify_workspace_state_token(
    *,
    administrator,
    account,
    token
):
    """
    Reject expired, manipulated or outdated
    workspace authorization submissions.
    """

    try:

        submitted_state = signing.loads(
            token,
            salt=WORKSPACE_STATE_SALT,
            max_age=WORKSPACE_STATE_MAX_AGE
        )

    except signing.BadSignature as exc:

        raise WorkspaceStateChangedError(
            "Your authorization form is invalid or "
            "has expired. Review the current workspace "
            "permissions before trying again."
        ) from exc

    current_state = get_workspace_authorization_state(
        account
    )

    expected_state = {
        "administrator_id": administrator.pk,
        "account_id": account.pk,
        "fingerprint": (
            _workspace_state_fingerprint(current_state)
        ),
    }

    if submitted_state != expected_state:

        raise WorkspaceStateChangedError(
            "The account's workspace authorization "
            "has changed since you opened this form. "
            "Review the current permissions before "
            "submitting another update."
        )

def can_manage_workspace_membership(administrator, account):
    """
    Determine whether an administrator may manage
    the target account's workspace membership.

    This policy is shared by the management service
    and the administrative interface.
    """

    administrator_profile = getattr(
        administrator,
        "profile",
        None
    )

    # Require both application Administrator authorization
    # and Django superuser authority.
    if (
        not administrator.is_authenticated
        or not administrator.is_active
        or not administrator.is_superuser
        or administrator_profile is None
        or administrator_profile.role != UserProfile.Role.ADMIN
    ):
        return False

    # Prevent administrators from granting or modifying
    # their own confidential workspace access.
    if administrator.pk == account.pk:
        return False

    return True


def get_workspace_memberships(account):
    """
    Return only the account's explicitly authorized
    Career Services workspace group memberships.
    """

    return tuple(
        account.groups.filter(
            name__in=WORKSPACE_GROUP_NAMES
        )
        .order_by("name")
        .values_list("name", flat=True)
    )

@account_identity_transaction()
def change_workspace_membership(
    *,
    administrator,
    account_id,
    membership,
    expected_state_token=None
):
    """
    Assign or revoke an account's workspace membership.

    Serialize authorization changes with other custom
    account management operations and remove historical
    project grants whenever membership changes.
    """

    User = get_user_model()

    if not administrator.is_authenticated:

        raise PermissionDenied(
            "Administrator authorization is required."
        )

    # Reload the acting administrator inside the
    # transaction to verify current authorization.
    current_administrator = (
        User.objects
        .select_related("profile")
        .filter(pk=administrator.pk)
        .first()
    )

    if current_administrator is None:

        raise PermissionDenied(
            "Administrator authorization is required."
        )

    # Retrieve the current target account.
    account = User.objects.get(
        pk=account_id
    )

    # Independently enforce the centralized policy.
    if not can_manage_workspace_membership(
        current_administrator,
        account
    ):

        raise PermissionDenied(
            "You are not authorized to manage "
            "this account's workspace membership."
        )

    # Administrative web submissions must match
    # the authorization state previously reviewed.
    #
    # Verify inside the transaction so cooperating
    # account management operations cannot intervene
    # between verification and persistence.
    if expected_state_token is not None:

        verify_workspace_state_token(
            administrator=current_administrator,
            account=account,
            token=expected_state_token
        )

    # Accept only explicitly approved workspace groups.
    if (
        membership != NO_WORKSPACE_ACCESS
        and membership not in WORKSPACE_GROUP_NAMES
    ):

        raise ValidationError(
            "Select a valid workspace membership."
        )

    selected_group = None

    if membership != NO_WORKSPACE_ACCESS:

        # Inactive accounts must not receive new
        # confidential workspace authorization.
        if not account.is_active:

            raise ValidationError(
                "An inactive account cannot be "
                "assigned workspace access."
            )

        try:

            selected_group = Group.objects.get(
                name=membership
            )

        except Group.DoesNotExist as exc:

            # Missing authorization groups indicate
            # an application configuration problem.
            raise ValidationError(
                "The selected workspace group "
                "is currently unavailable."
            ) from exc

        # Workspace groups must not silently introduce
        # additional Django model permissions.
        if selected_group.permissions.exists():

            raise ValidationError(
                "The selected workspace group "
                "has an invalid permission configuration."
            )

    current_memberships = get_workspace_memberships(
        account
    )

    desired_memberships = (
        ()
        if selected_group is None
        else (selected_group.name,)
    )

    # An unchanged authorized membership must preserve
    # existing project assignments.
    if current_memberships == desired_memberships:

        if selected_group is None:

            # An account without workspace membership
            # must not retain obsolete project grants.
            ProjectAccess.objects.filter(
                user_id=account.pk
            ).delete()

        return account

    # Retrieve only the three managed workspace groups.
    # All unrelated Django group memberships are preserved.
    existing_workspace_groups = list(
        account.groups.filter(
            name__in=WORKSPACE_GROUP_NAMES
        )
    )

    if existing_workspace_groups:

        account.groups.remove(
            *existing_workspace_groups
        )

    # Assign at most one authorized workspace group.
    if selected_group is not None:

        account.groups.add(
            selected_group
        )

    # Previous project assignments must not survive
    # a change in workspace authorization category.
    #
    # Fresh project grants must be explicitly assigned
    # if scoped workspace access is required again.
    ProjectAccess.objects.filter(
        user_id=account.pk
    ).delete()

    return account