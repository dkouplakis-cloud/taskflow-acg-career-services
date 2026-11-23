
"""
Django signals for the core application.

Automatically create a UserProfile when a
new user account is created.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="core_create_user_profile"
)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Give newly created users a Regular User profile.

    Existing users and profiles are not modified.
    """

    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "role": UserProfile.Role.REGULAR
            }
        )