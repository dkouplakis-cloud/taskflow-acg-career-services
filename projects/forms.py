
from django import forms
from django.utils import timezone

from core.models import TeamMember
from .models import Project


class ProjectForm(forms.ModelForm):
    """
    Handle project creation and editing.

    Require a project manager and allow selection
    of additional ACG Career Services team members.

    Prevent the manager from also being selected
    as a collaborator.
    """

    class Meta:
        model = Project

        # The Django account owner is assigned
        # by the view, never through the form.
        fields = [
            'name',
            'description',
            'status',
            'deadline',
            'project_manager',
            'collaborators',
        ]

        widgets = {
            'deadline': forms.DateInput(
                attrs={'type': 'date'}
            ),

            'collaborators': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only active Career Services team members
        # can be selected for new assignments.
        active_members = TeamMember.objects.filter(
            is_active=True
        )

        # A project must have a manager.
        self.fields['project_manager'].queryset = active_members
        self.fields['project_manager'].required = True
        self.fields['project_manager'].empty_label = (
            'Select a project manager'
        )

        # Allow selection of other team members.
        self.fields['collaborators'].queryset = active_members
        self.fields['collaborators'].required = False

        today = timezone.localdate()

        # Preserve unchanged overdue deadlines
        # when editing existing projects.
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
        Allow unchanged overdue deadlines.
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

    def clean(self):
        """
        Prevent a project manager from also
        being selected as a collaborator.
        """
        cleaned_data = super().clean()

        manager = cleaned_data.get('project_manager')
        collaborators = cleaned_data.get('collaborators')

        if (
            manager is not None
            and collaborators is not None
            and collaborators.filter(pk=manager.pk).exists()
        ):
            self.add_error(
                'collaborators',
                'The project manager cannot also '
                'be selected as a collaborator.'
            )

        return cleaned_data