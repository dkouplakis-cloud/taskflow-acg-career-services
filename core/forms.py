"""
TaskFlow | ACG Career Services

Django forms for the Core application.

ContactMessageForm validates Contact submissions
before they are saved to the database.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ContactMessage, StudentRegistrationRequest

class ContactMessageForm(forms.ModelForm):
    """
    Validate messages submitted through the
    TaskFlow Contact page.

    Validation is performed on the server,
    independently of JavaScript.
    """

    # Enforce the same message length limits
    # as the original frontend Contact form.
    message = forms.CharField(
        min_length=10,
        max_length=2000,
        strip=True,
        widget=forms.Textarea
    )

    class Meta:
        model = ContactMessage

        fields = [
            "name",
            "email",
            "subject",
            "message",
        ]

class StudentRegistrationForm(UserCreationForm):
    """
    Register students using Django's authentication system.

    Password validation is provided by UserCreationForm.
    New users receive regular profiles through the
    existing UserProfile creation signal.
    """

    # Require an email address for student accounts.
    email = forms.EmailField(
        required=True,
        label="Email Address"
    )

    # Require the student's real name for administrator review.
    first_name = forms.CharField(
        max_length=150,
        required=True,
        strip=True,
        label="First Name",
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        strip=True,
        label="Last Name",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()

        # Never expose roles or administrative privileges
        # through public student registration.
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

    def clean_email(self):
        """
        Prevent duplicate email addresses, including
        addresses that differ only by letter case.
        """

        email = self.cleaned_data["email"].strip().lower()

        User = get_user_model()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean(self):
        """
        Prevent duplicate pending registration requests.

        Rejected applications do not block a student
        from submitting a new registration request.
        """
        cleaned_data = super().clean()

        username = cleaned_data.get("username")
        email = cleaned_data.get("email")

        pending_requests = StudentRegistrationRequest.objects.filter(
            status=StudentRegistrationRequest.Status.PENDING
        )

        # A username cannot have multiple pending applications.
        if username and pending_requests.filter(
            username__iexact=username
        ).exists():
            self.add_error(
                "username",
                "A registration request for this username "
                "is already pending approval."
            )

        # Email comparisons must be case-insensitive.
        if email and pending_requests.filter(
            email__iexact=email
        ).exists():
            self.add_error(
                "email",
                "A registration request for this email "
                "address is already pending approval."
            )

        return cleaned_data