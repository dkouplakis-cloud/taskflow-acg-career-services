
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

class ProjectAccess(models.Model):
    """
    Grant an authorized account explicit access to a project.

    Career Services staff have office-wide access separately.
    These grants support scoped faculty and student assistants.
    """

    class AccessLevel(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        CONTRIBUTOR = "contributor", "Contributor"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="access_grants"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_access_grants"
    )

    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.VIEWER
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                name="unique_project_user_access"
            )
        ]

    def __str__(self):
        return (
            f"{self.user} - {self.project} "
            f"({self.get_access_level_display()})"
        )