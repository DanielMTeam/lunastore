"""Session locks serialize index writes across workers and management commands."""

from contextlib import contextmanager

from django.db import DEFAULT_DB_ALIAS, connections

from .indexes import APPLICATIONS_INDEX, USERS_INDEX

LOCK_NAMESPACE = 0x4C554E41
INDEX_LOCK_KEYS = {APPLICATIONS_INDEX: 1, USERS_INDEX: 2}


@contextmanager
def index_write_lock(index_uid, *, using=DEFAULT_DB_ALIAS, blocking=True):
    connection = connections[using]
    if connection.vendor != "postgresql":
        raise RuntimeError("Search index coordination requires PostgreSQL")
    key = INDEX_LOCK_KEYS[index_uid]
    with connection.cursor() as cursor:
        if blocking:
            cursor.execute("SELECT pg_advisory_lock(%s, %s)", [LOCK_NAMESPACE, key])
            acquired = True
        else:
            cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [LOCK_NAMESPACE, key])
            acquired = cursor.fetchone()[0]
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        # A lost connection releases session locks on the server automatically.
        if connection.connection is not None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [LOCK_NAMESPACE, key])
