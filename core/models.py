
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