
"""
Administrator-only student registration management.

Provide a secure review interface for pending
student account applications.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from .account_identity import AccountIdentityBusyError
from .models import StudentRegistrationRequest, UserProfile
from .permissions import role_required
from .registration_services import (
    RegistrationApprovalError,
    RegistrationRejectionError,
    approve_student_registration,
    reject_student_registration,
)


@role_required(UserProfile.Role.ADMIN)
@require_GET
def registration_request_list(request):
    """
    Display pending student registration applications.

    Only the Career Services Administrator can
    access this interface.

    Applications are ordered newest first and
    paginated for efficient administration.
    """

    # Prevent inactive accounts from reviewing
    # sensitive applicant information.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    pending_requests = (
        StudentRegistrationRequest.objects.filter(
            status=StudentRegistrationRequest.Status.PENDING
        )
        .order_by("-submitted_at", "-pk")
    )

    # Keep the interface manageable as the number
    # of registration applications increases.
    paginator = Paginator(pending_requests, 15)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "registration_management/request_list.html",
        {
            "page_title": "Student Registration Requests",
            "page_obj": page_obj,
            "pending_count": paginator.count,
        }
    )

@role_required(UserProfile.Role.ADMIN)
@require_GET
def registration_request_detail(request, pk):
    """
    Display a pending student registration for review.

    Only active administrators may inspect applications.
    Approval and rejection remain separate POST actions.
    """

    # Prevent inactive accounts from accessing
    # sensitive applicant information.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    # Only pending applications can be reviewed.
    # Missing or already-reviewed requests return HTTP 404.
    application = get_object_or_404(
        StudentRegistrationRequest,
        pk=pk,
        status=StudentRegistrationRequest.Status.PENDING,
    )

    return render(
        request,
        "registration_management/request_detail.html",
        {
            "page_title": "Review Student Registration",
            "application": application,
        },
    )

@role_required(UserProfile.Role.ADMIN)
@require_POST
def registration_request_approve(request, pk):
    """
    Approve a pending student registration.

    Only an active Administrator may approve requests.
    Account creation is delegated to the transactional
    registration approval service.
    """

    # Reject inactive administrator accounts.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    # Return HTTP 404 for nonexistent applications.
    application = get_object_or_404(
        StudentRegistrationRequest,
        pk=pk,
    )

    try:
        # The service independently verifies authorization,
        # application status, and account uniqueness.
        approve_student_registration(
            application_id=application.pk,
            reviewer=request.user,
        )

    except AccountIdentityBusyError:

        # Preserve the pending application when
        # the approval transaction cannot proceed.
        messages.error(
            request,
            "Registration approval is temporarily unavailable. "
            "Please try again in a moment."
        )

    except (RegistrationApprovalError, ValidationError) as exc:
        # Display validation or application-state errors
        # without creating an account.
        messages.error(
            request,
            f"Registration could not be approved: {exc}"
        )

    except IntegrityError:
        # Handle a database integrity conflict without
        # exposing internal database error details.
        messages.error(
            request,
            "Registration could not be approved because "
            "of a database conflict."
        )

    else:
        messages.success(
            request,
            "Student registration approved successfully. "
            "The student account is now active."
        )

    # Follow the Post/Redirect/Get pattern.
    return redirect(
        "registration_management:request_list"
    )

@role_required(UserProfile.Role.ADMIN)
@require_POST
def registration_request_reject(request, pk):
    """
    Reject a pending student registration request.

    Only an active Administrator may reject applications.
    The rejection service records the review decision
    without creating a Django user account.
    """

    # Prevent inactive administrator accounts
    # from reviewing student applications.
    if not request.user.is_active:
        raise PermissionDenied(
            "An active administrator account is required."
        )

    # Return HTTP 404 for nonexistent applications.
    application = get_object_or_404(
        StudentRegistrationRequest,
        pk=pk,
    )

    try:
        # The service independently checks authorization
        # and ensures the application is still pending.
        reject_student_registration(
            application_id=application.pk,
            reviewer=request.user,
        )

    except AccountIdentityBusyError:

        # Preserve the pending application when
        # the rejection transaction cannot proceed.
        messages.error(
            request,
            "Registration rejection is temporarily unavailable. "
            "Please try again in a moment."
        )

    except RegistrationRejectionError as exc:
        # Preserve the original review decision
        # and display a helpful error message.
        messages.error(
            request,
            f"Registration could not be rejected: {exc}"
        )

    else:
        messages.success(
            request,
            "Student registration rejected successfully. "
            "No student account was created."
        )

    # Follow the Post/Redirect/Get pattern.
    return redirect(
        "registration_management:request_list"
    )