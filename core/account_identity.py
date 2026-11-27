
"""
Shared transaction handling for TaskFlow account identities.

Coordinate operations involving registered usernames,
email addresses and pending registration requests.
"""

from contextlib import contextmanager

from django.db import transaction
from django.db.models import F

from .models import AccountIdentityLock


@contextmanager
def account_identity_transaction():
    """
    Serialize participating account identity operations.

    The synchronization row must be updated before
    performing account identity validation or persistence.

    The surrounding transaction retains the database
    lock until the operation commits or rolls back.
    """

    with transaction.atomic():

        # Acquire a database write lock before reading
        # or validating account identity information.
        updated_rows = AccountIdentityLock.objects.filter(
            pk=1
        ).update(
            revision=F("revision") + 1
        )

        # Restore the synchronization record if it is
        # missing following a database flush or reset.
        if updated_rows == 0:

            AccountIdentityLock.objects.get_or_create(
                pk=1,
                defaults={"revision": 0}
            )

            # Acquire the lock on the restored record.
            AccountIdentityLock.objects.filter(
                pk=1
            ).update(
                revision=F("revision") + 1
            )

        # Execute the caller's protected operation
        # within the same atomic database transaction.
        yield