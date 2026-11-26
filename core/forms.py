"""
TaskFlow | ACG Career Services

Django forms for the Core application.

ContactMessageForm validates Contact submissions
before they are saved to the database.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import ContactMessage


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