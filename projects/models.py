
from django.conf import settings
from django.db import models


class Project(models.Model):

    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        ACTIVE = 'active', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    
    # Django account that owns the project.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )

    # Staff member responsible for managing the project.
    project_manager = models.ForeignKey(
        'core.TeamMember',
        on_delete=models.PROTECT,
        related_name='managed_projects',
        null=True,
        blank=True
    )

    # Other staff members collaborating on the project.
    collaborators = models.ManyToManyField(
        'core.TeamMember',
        related_name='collaborating_projects',
        blank=True
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED
    )

    deadline = models.DateField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name