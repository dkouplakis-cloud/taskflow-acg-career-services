
from django import forms
from django.utils import timezone

from core.models import TeamMember
from .models import Task


class TaskForm(forms.ModelForm):
    """
    Create and edit tasks within a specific project.

    Only the project's manager and collaborators
    can be selected as task assignees.
    """

    class Meta:
        model = Task

        # The project is assigned by the Django view.
        fields = [
            'name',
            'description',
            'status',
            'priority',
            'due_date',
            'assignee',
        ]

        widgets = {
            'due_date': forms.DateInput(
                attrs={'type': 'date'}
            ),

            'description': forms.Textarea(
                attrs={'rows': 5}
            ),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        if project is None:
            raise ValueError(
                'TaskForm requires a project.'
            )

        self.project = project

        # Collect the project's collaborators.
        allowed_ids = list(
            project.collaborators.values_list(
                'pk',
                flat=True
            )
        )

        # Include the project manager.
        if project.project_manager_id:
            allowed_ids.append(
                project.project_manager_id
            )

        # Only active project participants
        # can receive task assignments.
        eligible_members = TeamMember.objects.filter(
            pk__in=allowed_ids,
            is_active=True
        ).order_by('full_name')

        self.fields['assignee'].queryset = (
            eligible_members
        )

        # Mandatory even while the database field
        # temporarily allows NULL values.
        self.fields['assignee'].required = True

        self.fields['assignee'].empty_label = (
            'Select a team member'
        )

        # Preserve unchanged overdue dates
        # when editing existing tasks.
        existing_date = (
            self.instance.due_date
            if self.instance.pk
            else None
        )

        if (
            existing_date is None
            or existing_date >= timezone.localdate()
        ):
            self.fields['due_date'].widget.attrs[
                'min'
            ] = timezone.localdate().isoformat()

    def clean_due_date(self):
        """
        Prevent newly selected past due dates.
        Allow unchanged overdue dates during editing.
        """
        due_date = self.cleaned_data.get(
            'due_date'
        )

        if due_date is None:
            return due_date

        existing_date = (
            self.instance.due_date
            if self.instance.pk
            else None
        )

        if (
            due_date < timezone.localdate()
            and due_date != existing_date
        ):
            raise forms.ValidationError(
                'Please select today or a future date.'
            )

        return due_date