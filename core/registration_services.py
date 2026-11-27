"""
Business logic for administrator-reviewed registrations.

Student accounts are created only after an authorized
administrator approves a pending application.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import StudentRegistrationRequest, UserProfile


class RegistrationApprovalError(Exception):
    """Raised when an application cannot be approved."""


@transaction.atomic
def approve_student_registration(*, application_id, reviewer):
    """
    Approve a pending registration and create a student.

    The operation is atomic: account creation and the
    registration decision succeed or fail together.
    """

    # Enforce authorization at the service layer too.
    if (
        not reviewer.is_authenticated
        or not reviewer.is_active
        or not UserProfile.objects.filter(
            user=reviewer,
            role=UserProfile.Role.ADMIN
        ).exists()
    ):
        raise PermissionDenied(
            "Administrator authorization is required."
        )

    # Lock the application row where supported.
    application = (
        StudentRegistrationRequest.objects
        .select_for_update()
        .get(pk=application_id)
    )

    if application.status != StudentRegistrationRequest.Status.PENDING:
        raise RegistrationApprovalError(
            "This registration has already been reviewed."
        )

    User = get_user_model()

    # Recheck uniqueness because another account may
    # have been created after the student applied.
    if User.objects.filter(
        username__iexact=application.username
    ).exists():
        raise RegistrationApprovalError(
            "This username is already registered."
        )

    if User.objects.filter(
        email__iexact=application.email
    ).exists():
        raise RegistrationApprovalError(
            "This email address is already registered."
        )

    if not application.password_hash:
        raise RegistrationApprovalError(
            "The application has no stored password hash."
        )

    # The password is already hashed by make_password().
    # Assigning the existing hash avoids hashing it twice.
    student = User(
        username=application.username,
        first_name=application.first_name,
        last_name=application.last_name,
        email=User.objects.normalize_email(
            application.email
        ),
        password=application.password_hash,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )

    student.full_clean()
    student.save()

    # The existing post_save signal automatically
    # creates the student's Regular User profile.
    application.status = StudentRegistrationRequest.Status.APPROVED
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()

    # Remove the password hash from the review record.
    application.password_hash = ""

    application.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "password_hash",
        ]
    )

    return student

class RegistrationRejectionError(Exception):
    """Raised when an application cannot be rejected."""


@transaction.atomic
def reject_student_registration(*, application_id, reviewer):
    """
    Reject a pending student registration request.

    Record the administrator's decision without
    creating a Django user account.
    """

    # Enforce administrator authorization at
    # the business-logic layer.
    if (
        not reviewer.is_authenticated
        or not reviewer.is_active
        or not UserProfile.objects.filter(
            user=reviewer,
            role=UserProfile.Role.ADMIN
        ).exists()
    ):
        raise PermissionDenied(
            "Administrator authorization is required."
        )

    # Lock the request where database support exists.
    application = (
        StudentRegistrationRequest.objects
        .select_for_update()
        .get(pk=application_id)
    )

    # Reviewed applications must not be modified again.
    if application.status != StudentRegistrationRequest.Status.PENDING:
        raise RegistrationRejectionError(
            "This registration has already been reviewed."
        )

    # Record the rejection decision.
    application.status = StudentRegistrationRequest.Status.REJECTED
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()

    # Retaining a rejected applicant's password
    # hash serves no further authentication purpose.
    application.password_hash = ""

    application.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "password_hash",
        ]
    )

    return application