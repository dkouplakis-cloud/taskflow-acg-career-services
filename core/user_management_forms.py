
"""
Validated forms for TaskFlow's custom user administration.

Keep administrative account management separate
from public student registration and profile forms.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import StudentRegistrationRequest, UserProfile


class UserDirectoryFilterForm(forms.Form):
    """
    Validate account directory search and filter parameters.
    """

    # Search registered account identity information.
    q = forms.CharField(
        label="Search users",
        required=False,
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search name, username or email...",
                "maxlength": "150",
                "type": "search",
            }
        ),
    )

    # Reuse the application's existing role definitions.
    role = forms.ChoiceField(
        label="Application role",
        required=False,
        choices=[
            ("", "All Roles"),
            *UserProfile.Role.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # Restrict account status to supported values.
    status = forms.ChoiceField(
        label="Account status",
        required=False,
        choices=[
            ("", "All Statuses"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

class AdminUserCreationForm(UserCreationForm):
    """
    Validate new accounts created through TaskFlow's
    custom administration interface.

    Reuse Django's credential validation and secure
    password handling instead of implementing them manually.
    """

    first_name = forms.CharField(
        label="First name",
        required=True,
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter first name",
                "autocomplete": "off",
            }
        ),
    )

    last_name = forms.CharField(
        label="Last name",
        required=True,
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter last name",
                "autocomplete": "off",
            }
        ),
    )

    email = forms.EmailField(
        label="Email address",
        required=True,
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Enter email address",
                "autocomplete": "off",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):

        model = get_user_model()

        # Explicitly allow only account identity and credentials.
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        """
        Apply consistent administration form styling.
        """

        super().__init__(*args, **kwargs)

        # Reuse the existing administration form styles.
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

        # Avoid suggesting the administrator's own credentials.
        self.fields["username"].widget.attrs.update({
            "placeholder": "Choose a unique username",
            "autocomplete": "off",
        })

        self.fields["password1"].widget.attrs.update({
            "placeholder": "Enter a secure password",
            "autocomplete": "new-password",
        })

        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm the password",
            "autocomplete": "new-password",
        })

    def clean_email(self):
        """
        Prevent duplicate registered email addresses,
        including differences in letter casing.
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
        Prevent direct account creation from conflicting
        with pending student registration requests.
        """

        cleaned_data = super().clean()

        username = cleaned_data.get("username")
        email = cleaned_data.get("email")

        # Pending applications reserve their requested
        # username and email until an administrator
        # completes the registration review.
        pending_requests = StudentRegistrationRequest.objects.filter(
            status=StudentRegistrationRequest.Status.PENDING
        )

        # Prevent conflicts with pending usernames.
        if username and pending_requests.filter(
            username__iexact=username
        ).exists():

            self.add_error(
                "username",
                "A registration request for this username "
                "is already pending approval. Review the "
                "registration request before creating an account."
            )

        # Prevent conflicts with pending email addresses.
        if email and pending_requests.filter(
            email__iexact=email
        ).exists():

            self.add_error(
                "email",
                "A registration request for this email address "
                "is already pending approval. Review the "
                "registration request before creating an account."
            )

        return cleaned_data