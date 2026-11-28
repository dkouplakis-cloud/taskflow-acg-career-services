
"""
Validated forms for TaskFlow's custom user administration.

Keep administrative account management separate
from public student registration and profile forms.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    UserCreationForm,
    UsernameField,
)
from .models import StudentRegistrationRequest, UserProfile
from .user_role_services import get_assignable_roles
from .permissions import WORKSPACE_GROUP_NAMES
from .user_workspace_services import (
    NO_WORKSPACE_ACCESS,
    can_manage_workspace_membership,
    get_workspace_memberships,
)

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

class AdminUserEditForm(forms.ModelForm):
    """
    Validate identity changes to an existing account
    through TaskFlow's custom administration interface.

    Application roles, workspace memberships and Django
    authentication privileges are managed separately.
    """

    class Meta:

        model = get_user_model()

        # Explicitly restrict the editable account fields.
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
        )

        # Preserve Django's username normalization.
        field_classes = {
            "username": UsernameField,
        }

        widgets = {
            "username": forms.TextInput(
                attrs={
                    "placeholder": "Enter username",
                    "autocomplete": "off",
                }
            ),

            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "Enter first name",
                    "autocomplete": "off",
                }
            ),

            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "Enter last name",
                    "autocomplete": "off",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "placeholder": "Enter email address",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        """
        Configure the existing account editing form
        using consistent administrative field styling.
        """

        super().__init__(*args, **kwargs)

        # This form must only edit existing accounts.
        # New accounts use AdminUserCreationForm.
        if self.instance.pk is None:
            raise ValueError(
                "An existing user account is required."
            )

        # Maintain the same required identity fields
        # as the administrative account creation form.
        for field in self.fields.values():

            field.required = True

            field.widget.attrs["class"] = (
                "form-control"
            )

    def clean_username(self):
        """
        Prevent duplicate registered usernames
        and conflicts with pending registrations.
        """

        username = self.cleaned_data["username"]

        User = get_user_model()

        # Exclude the account currently being edited.
        existing_accounts = User.objects.exclude(
            pk=self.instance.pk
        )

        if existing_accounts.filter(
            username__iexact=username
        ).exists():

            raise forms.ValidationError(
                "An account with this username "
                "already exists."
            )

        # Pending applications reserve their requested
        # usernames until an administrator reviews them.
        if StudentRegistrationRequest.objects.filter(
            status=StudentRegistrationRequest.Status.PENDING,
            username__iexact=username
        ).exists():

            raise forms.ValidationError(
                "A registration request for this username "
                "is already pending approval."
            )

        return username

    def clean_email(self):
        """
        Normalize email addresses and prevent conflicts
        with registered accounts and pending applications.
        """

        email = (
            self.cleaned_data["email"]
            .strip()
            .lower()
        )

        User = get_user_model()

        # The account may retain its own email address.
        existing_accounts = User.objects.exclude(
            pk=self.instance.pk
        )

        if existing_accounts.filter(
            email__iexact=email
        ).exists():

            raise forms.ValidationError(
                "An account with this email address "
                "already exists."
            )

        # Preserve pending registration reservations.
        if StudentRegistrationRequest.objects.filter(
            status=StudentRegistrationRequest.Status.PENDING,
            email__iexact=email
        ).exists():

            raise forms.ValidationError(
                "A registration request for this email "
                "address is already pending approval."
            )

        return email

class AdminUserRoleForm(forms.Form):
    """
    Validate administrative application role assignments.

    Available role choices are determined by the
    requesting administrator's assignment authority.

    Actual role changes are performed exclusively
    through the transactional role management service.
    """

    role = forms.ChoiceField(
        label="Application role",
        choices=(),
        required=True,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        help_text=(
            "Select the application role to assign "
            "to this account."
        ),
        error_messages={
            "required": (
                "Select an application role."
            ),
            "invalid_choice": (
                "You are not authorized to assign "
                "the selected role, or the role "
                "does not exist."
            ),
        }
    )

    def __init__(
        self,
        *args,
        administrator,
        account,
        **kwargs
    ):
        """
        Restrict the available role choices using
        the centralized authorization policy.
        """

        super().__init__(*args, **kwargs)

        self.administrator = administrator
        self.account = account

        # Retrieve the roles that this administrator
        # is authorized to assign to the target account.
        self.assignable_roles = get_assignable_roles(
            administrator,
            account
        )

        # Reuse the existing model labels rather than
        # maintaining duplicate role definitions.
        role_labels = dict(
            UserProfile.Role.choices
        )

        self.fields["role"].choices = [
            (role, role_labels[role])
            for role in self.assignable_roles
        ]

        # Preselect the account's existing role
        # when displaying an authorized form.
        profile = getattr(
            account,
            "profile",
            None
        )

        if (
            profile is not None
            and profile.role in self.assignable_roles
        ):

            self.initial.setdefault(
                "role",
                profile.role
            )

    def clean(self):
        """
        Reject role modification when the requesting
        administrator has no assignment authority.
        """

        cleaned_data = super().clean()

        if not self.assignable_roles:

            raise forms.ValidationError(
                "You are not authorized to modify "
                "this account's application role."
            )

        return cleaned_data

class AdminUserWorkspaceForm(forms.Form):
    """
    Validate administrative workspace membership updates.

    Workspace authorization remains independent of
    application roles and Django authentication privileges.

    Actual membership changes are performed exclusively
    through the transactional workspace management service.
    """

    # Preserve the authorization state reviewed
    # when the administrator originally opened the form.
    state_token = forms.CharField(
        required=True,
        max_length=1024,
        widget=forms.HiddenInput(),
        error_messages={
            "required": (
                "The authorization state is missing. "
                "Reload this page before continuing."
            ),
            "max_length": (
                "The authorization state is invalid. "
                "Reload this page before continuing."
            ),
        }
    )

    membership = forms.ChoiceField(
        label="Workspace membership",
        choices=(),
        required=True,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        help_text=(
            "Select the account's authorized "
            "Career Services workspace membership."
        ),
        error_messages={
            "required": (
                "Select a workspace membership."
            ),
            "invalid_choice": (
                "The selected workspace membership "
                "is invalid or unavailable for this account."
            ),
        }
    )

    confirm_change = forms.BooleanField(
        label=(
            "I understand the consequences "
            "of this membership update."
        ),
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        help_text=(
            "Changing or revoking workspace membership "
            "removes existing project assignments. "
            "Selecting no workspace access also removes "
            "any remaining obsolete project grants."
        ),
        error_messages={
            "required": (
                "Confirm that you understand the "
                "consequences before continuing."
            ),
        }
    )

    def __init__(
        self,
        *args,
        administrator,
        account,
        **kwargs
    ):
        """
        Configure membership choices according to
        administrator authority and account status.
        """

        super().__init__(*args, **kwargs)

        self.administrator = administrator
        self.account = account

        # Reuse the centralized workspace management
        # authorization policy.
        self.can_manage_membership = (
            can_manage_workspace_membership(
                administrator,
                account
            )
        )

        # Retrieve the account's existing authorized
        # workspace memberships.
        self.current_memberships = (
            get_workspace_memberships(account)
        )

        # Unauthorized administrators receive no
        # available membership choices.
        if not self.can_manage_membership:

            return

        # Require an explicit selection when an existing
        # account has an ambiguous membership configuration.
        membership_choices = [
            ("", "Select workspace membership"),
            (
                NO_WORKSPACE_ACCESS,
                "No workspace access"
            ),
        ]

        # Only active accounts may receive workspace
        # membership. Inactive accounts may have their
        # existing access revoked.
        if account.is_active:

            membership_choices.extend(
                (group_name, group_name)
                for group_name in WORKSPACE_GROUP_NAMES
            )

        self.fields["membership"].choices = (
            membership_choices
        )

        # Preselect the existing membership only when
        # the account has an unambiguous valid state.
        if not self.current_memberships:

            self.initial.setdefault(
                "membership",
                NO_WORKSPACE_ACCESS
            )

        elif (
            account.is_active
            and len(self.current_memberships) == 1
        ):

            self.initial.setdefault(
                "membership",
                self.current_memberships[0]
            )

        # Multiple existing memberships or an inactive
        # account with membership require explicit review.
        else:

            self.initial.setdefault(
                "membership",
                ""
            )

    def clean(self):
        """
        Reject unauthorized membership submissions.
        """

        cleaned_data = super().clean()

        if not self.can_manage_membership:

            raise forms.ValidationError(
                "You are not authorized to manage "
                "this account's workspace membership."
            )

        return cleaned_data