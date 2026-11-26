
"""
Custom authentication views for TaskFlow.

Provide role-aware login redirection while
preserving Django's built-in authentication
and safe redirect handling.
"""

from django.contrib.auth.views import LoginView
from django.urls import reverse

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .forms import StudentRegistrationForm
from .models import UserProfile


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

        is_administrator = UserProfile.objects.filter(
            user=self.request.user,
            role=UserProfile.Role.ADMIN
        ).exists()

        if is_administrator:
            return reverse(
                "catalog_management:dashboard"
            )

        return super().get_default_redirect_url()

@login_not_required
@require_http_methods(["GET", "POST"])
def student_register(request):
    """
    Allow visitors to create regular student accounts.

    Registration never assigns privileged workspace
    groups or administrative permissions.
    """

    # Existing users do not need another account.
    if request.user.is_authenticated:
        return redirect("catalog:list")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            # Create the account and its signal-generated
            # profile within one database transaction.
            with transaction.atomic():
                user = form.save()

            # Sign in the newly registered student.
            login(request, user)

            messages.success(
                request,
                "Your account has been created successfully."
            )

            return redirect("catalog:list")

    else:
        form = StudentRegistrationForm()

    # Display the form or its validation errors.
    return render(
        request,
        "registration/student_register.html",
        {"form": form}
    )