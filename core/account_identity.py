
"""
Shared transaction handling for TaskFlow account identities.

Coordinate operations involving registered usernames,
email addresses and pending registration requests.
"""

import sqlite3

from contextlib import contextmanager

from django.db import (
    connection,
    OperationalError,
    transaction,
)

from django.db.models import F

from .models import AccountIdentityLock


class AccountIdentityBusyError(Exception):
    """
    Raised when an account identity operation cannot
    proceed because the database is temporarily locked.
    """


def is_account_database_contention(error):
    """
    Identify temporary SQLite database lock contention
    without suppressing unrelated database failures.
    """

    # The current TaskFlow database backend is SQLite.
    # Other database backends require their own handling.
    if connection.vendor != "sqlite":
        return False

    original_error = error.__cause__

    # Prefer SQLite's native error codes where available.
    error_code = getattr(
        original_error,
        "sqlite_errorcode",
        None
    )

    if error_code is not None:

        # Extended SQLite error codes retain the primary
        # result code in their lowest eight bits.
        primary_code = error_code & 0xFF

        return primary_code in (
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        )

    # Compatibility fallback for environments where
    # native SQLite error codes are unavailable.
    error_message = str(
        original_error or error
    ).strip().lower()

    return (
        error_message == "database is locked"
        or error_message == "database table is locked"
        or error_message.startswith(
            "database table is locked:"
        )
        or error_message == "database schema is locked"
        or error_message.startswith(
            "database schema is locked:"
        )
    )


@contextmanager
def account_identity_transaction():
    """
    Serialize participating account identity operations.

    Acquire the synchronization lock before validating
    or persisting account identity information.

    Translate temporary database lock contention into
    a controlled application-level exception.
    """

    try:

        with transaction.atomic():

            # Acquire the shared database write lock.
            updated_rows = (
                AccountIdentityLock.objects
                .filter(pk=1)
                .update(revision=F("revision") + 1)
            )

            # Recover the singleton record following
            # database resets or test database flushes.
            if updated_rows == 0:

                AccountIdentityLock.objects.get_or_create(
                    pk=1,
                    defaults={"revision": 0}
                )

                AccountIdentityLock.objects.filter(
                    pk=1
                ).update(
                    revision=F("revision") + 1
                )

            # Execute the caller's protected operation.
            yield

    except OperationalError as error:

        # The atomic transaction has already exited,
        # allowing unsuccessful changes to roll back.
        if is_account_database_contention(error):

            raise AccountIdentityBusyError(
                "Account management is temporarily busy. "
                "Please try again."
            ) from error

        # Unexpected database failures must remain
        # visible to Django's normal error handling.
        raise