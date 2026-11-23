
"""
Custom authentication views for TaskFlow.

Provide role-aware login redirection while
preserving Django's built-in authentication
and safe redirect handling.
"""

from django.contrib.auth.views import LoginView
from django.urls import reverse

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