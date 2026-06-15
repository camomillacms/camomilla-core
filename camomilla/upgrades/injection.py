"""Generic registry for auto-injecting camomilla data-migration operations
into the migrations ``makemigrations`` generates.

Used by the ``camomilla_makemigrations`` management command. This module knows
nothing about any specific upgrade — each upgrade module registers an
*injector* with :func:`register_injector` (defined next to its operation). An
injector inspects a freshly-autodetected ``Migration`` and, when its breaking
change is detected, inserts the operation at the correct position and returns a
short label for reporting (``None`` when it doesn't apply).

Adding a future upgrade therefore touches only that upgrade's own module — see
``status_to_lifecycle.py`` for the reference example.
"""


_INJECTORS = []


def register_injector(fn):
    """Register ``fn`` as an injector. Use as a decorator on the injector
    defined alongside an upgrade's operation. An injector inspects a migration,
    inserts its operation(s) when its breaking change is detected, and returns a
    **list of labels** for what it inserted (empty list when it doesn't apply)::

        @register_injector
        def inject_my_change(migration):
            if not _applies(migration):
                return []
            migration.operations = ...   # insert the op(s)
            return ["MyOperation"]

    Injectors run in registration order. Registering the same callable twice is
    a no-op (keeps imports idempotent).
    """
    if fn not in _INJECTORS:
        _INJECTORS.append(fn)
    return fn


def inject_upgrade_operations(migration):
    """Run every registered injector against ``migration`` (mutating it in
    place). Returns the flat list of inserted operation labels — empty when
    nothing applied."""
    inserted = []
    for injector in _INJECTORS:
        inserted.extend(injector(migration) or [])
    return inserted
