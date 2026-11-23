from django.conf import settings
from django.db import models


class ContactMessage(models.Model):
    """
    Store contact messages submitted through TaskFlow.

    Messages are validated by Django before
    being saved to the database.
    """

    class Subject(models.TextChoices):
        FEEDBACK = "feedback", "General Feedback"
        SUGGESTION = "suggestion", "Feature Suggestion"
        ISSUE = "issue", "Report an Issue"
        OTHER = "other", "Other"

    name = models.CharField(
        max_length=100
    )

    email = models.EmailField(
        max_length=150
    )

    subject = models.CharField(
        max_length=20,
        choices=Subject.choices
    )

    message = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.name} - "
            f"{self.get_subject_display()}"
    )

class TeamMember(models.Model):
    """
    Represent a member of the ACG Career Services team.

    Team members can serve as project managers,
    project collaborators, and task assignees.
    """

    full_name = models.CharField(
        max_length=120,
        unique=True
    )

    job_title = models.CharField(
        max_length=120
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return self.full_name
    

    @property
    def initials(self):
        """
        Return the first two name initials.
        Example: Alexandra Prindezi -> AP
        """
        parts = self.full_name.strip().split()

        return "".join(
            part[0].upper() for part in parts[:2]
        ) or "?"

    @property
    def avatar_tone(self):
        """
        Assign a consistent avatar color
        to each Career Services team member.
        """
        tones = {
            "Alexandra Prindezi": "violet",
            "Dimitris Megremis": "blue",
            "Efthimis Charokopos": "teal",
            "Elina Krithari": "rose",
            "Marina Perantonaki": "amber",
        }

        return tones.get(
            self.full_name.strip(),
            "slate"
        )

class UserProfile(models.Model):
    """
    Extend Django's existing authentication system
    with user roles and profile information.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        POWER = "power", "Power User"
        REGULAR = "regular", "Regular User"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REGULAR
    )

    bio = models.TextField(
        max_length=1000,
        blank=True
    )

    avatar = models.ImageField(
        upload_to="profiles/avatars/",
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.get_role_display()}"
        )