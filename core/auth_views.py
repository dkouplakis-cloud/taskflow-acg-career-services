
"""
Custom authentication views for TaskFlow.

Provide role-aware login redirection while
preserving Django's built-in authentication
and safe redirect handling.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .account_identity import account_identity_transaction
from .forms import StudentRegistrationForm
from .models import StudentRegistrationRequest, UserProfile
from .permissions import can_access_workspace

class TaskFlowLoginView(LoginView):
    """
    Redirect Administrators to their management
    dashboard after a normal login.

    Other users retain the standard TaskFlow
    login destination.

    Django's existing handling of the 'next'
    parameter remains unchanged.
    """

    def get_default_redirect_url(self):
        """
        Redirect users according to their authorized portal.

        Administrators access catalogue management.
        Authorized workspace members retain their
        existing internal destination.
        Regular students access the public catalogue.

        Django's safe 'next' handling remains unchanged.
        """

        user = self.request.user

        # Administrators access their management dashboard.
        is_administrator = UserProfile.objects.filter(
            user=user,
            role=UserProfile.Role.ADMIN
        ).exists()

        if is_administrator:
            return reverse("catalog_management:dashboard")

        # Ordinary students must not be redirected
        # to the restricted Projects workspace.
        if not can_access_workspace(user):
            return reverse("catalog:list")

        # Preserve the existing destination for
        # explicitly authorized workspace personnel.
        return super().get_default_redirect_url()

@login_not_required
@require_http_methods(["GET", "POST"])
def student_register(request):
    """
    Accept student registration applications.

    A student account is not created until the
    Career Services Administrator approves it.

    Coordinate identifier validation and persistence
    with other account identity management operations.
    """

    # Authenticated users cannot submit new applications.
    if request.user.is_authenticated:
        return redirect("catalog:list")

    if request.method == "POST":

        form = StudentRegistrationForm(request.POST)

        application_created = False

        try:

            # Acquire the shared synchronization lock
            # before performing registration validation.
            with account_identity_transaction():

                if form.is_valid():

                    # Store only the hashed password.
                    StudentRegistrationRequest.objects.create(
                        username=form.cleaned_data["username"],
                        first_name=form.cleaned_data["first_name"],
                        last_name=form.cleaned_data["last_name"],
                        email=form.cleaned_data["email"],
                        password_hash=make_password(
                            form.cleaned_data["password1"]
                        ),
                        status=StudentRegistrationRequest.Status.PENDING,
                    )

                    application_created = True

        except IntegrityError:

            # Handle database uniqueness conflicts
            # without exposing internal database details.
            form.add_error(
                None,
                "This registration request could not be "
                "submitted because the username or email "
                "may already be registered or reserved "
                "by a pending application. Please review "
                "your details and try again."
            )

        else:

            # Display success only after the protected
            # transaction completes successfully.
            if application_created:

                messages.success(
                    request,
                    "Your registration request has been submitted "
                    "for administrator approval. You will be able "
                    "to sign in only after your account is approved."
                )

                # Applicants remain unauthenticated until approval.
                return redirect("student_register")

    else:

        form = StudentRegistrationForm()

    return render(
        request,
        "registration/student_register.html",
        {"form": form}
    )