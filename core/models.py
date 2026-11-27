from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

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

class StudentRegistrationRequest(models.Model):
    """
    Store student account applications awaiting
    approval from the Career Services Administrator.

    A Django User is created only after approval.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    # Information submitted by the prospective student.
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()

    # Store only Django's password hash, never plaintext.
    # This field will be cleared after review.
    password_hash = models.CharField(
        max_length=128,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    # Record which administrator reviewed the application.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_student_registrations"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-submitted_at"]

        # Enforce case-insensitive uniqueness only
        # while applications are pending.
        #
        # Reviewed applications remain available
        # for administrative history and auditing.
        constraints = [
            models.UniqueConstraint(
                Lower("username"),
                condition=models.Q(status="pending"),
                name="core_pending_username_ci",
            ),
            models.UniqueConstraint(
                Lower("email"),
                condition=models.Q(status="pending"),
                name="core_pending_email_ci",
            ),
        ]

    def __str__(self):
        return f"{self.username} - {self.get_status_display()}"

class AccountIdentityLock(models.Model):
    """
    Provide a shared database-backed synchronization
    point for account identity management.

    Operations that create or modify account identifiers
    must acquire this lock before validating and
    persisting usernames and email addresses.

    Only one synchronization record is permitted.
    """

    # Fixed identifier for the shared synchronization row.
    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False
    )

    # Updating this value acquires a database write lock
    # within the surrounding atomic transaction.
    revision = models.PositiveBigIntegerField(
        default=0,
        editable=False
    )

    class Meta:

        verbose_name = "Account identity lock"
        verbose_name_plural = "Account identity locks"

        # Prevent multiple synchronization records.
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="core_identity_lock_singleton",
            ),
        ]

    def __str__(self):
        return "Account identity synchronization lock"