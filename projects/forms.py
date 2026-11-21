from django import forms
from django.utils import timezone

from .models import Project


class ProjectForm(forms.ModelForm):
    """
    Handle project creation and editing using one reusable form.
    Validate deadlines before saving project information.
    """

    class Meta:
        model = Project

        # Ownership is assigned by the view, never by the user.
        fields = [
            'name',
            'description',
            'status',
            'deadline',
        ]

        # Display a native date picker in the browser.
        widgets = {
            'deadline': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        today = timezone.localdate()

        # Prevent selecting past dates in the date picker.
        # Preserve existing overdue dates during editing.
        existing_deadline = (
            self.instance.deadline if self.instance.pk else None
        )

        if not existing_deadline or existing_deadline >= today:
            self.fields['deadline'].widget.attrs['min'] = (
                today.isoformat()
            )

    def clean_deadline(self):
        """
        Reject newly selected past deadlines.
        Allow an unchanged overdue deadline while editing.
        """
        deadline = self.cleaned_data.get('deadline')

        if deadline is None:
            return deadline

        existing_deadline = (
            self.instance.deadline if self.instance.pk else None
        )

        if (
            deadline < timezone.localdate()
            and deadline != existing_deadline
        ):
            raise forms.ValidationError(
                'Please select today or a future date.'
            )

        return deadline
