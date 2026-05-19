"""
Page drafting, scheduling and revision helpers.

Drafts are stored as a JSON overlay (``draft_data``) on each page instance.
The live row is always the published content; the overlay accumulates pending
edits until an editor decides to publish, schedule or discard them.

Preview is **author/admin only** and exposed through the dedicated
``/pages/{id}/preview/`` and ``/pages/{id}/render/`` viewset actions, which
inherit DRF model permissions. There is no public preview path: the public
router serves only published content (with the read-time scheduled-swap
overlay applied automatically when due).

Revision history is backed by ``django-reversion``: each publish creates a
revision so editors can revert to any previous published state.
"""

from __future__ import annotations


def reversion_available() -> bool:
    try:
        import reversion  # noqa: F401
    except ImportError:
        return False
    from django.conf import settings as django_settings

    return "reversion" in django_settings.INSTALLED_APPS


def register_page_for_revisions(model_cls) -> None:
    """Register a concrete AbstractPage subclass with django-reversion.

    Note: ``UrlNode`` is intentionally NOT followed here. Following it would
    make reversion try to revert the url_node row in parallel with the page,
    but ``AbstractPage.save`` runs ``_update_url_node`` on every save (to keep
    permalinks/redirects consistent), which conflicts with the in-flight
    revert and raises ``RevertError``. As a consequence, reverting a page
    whose permalink was manually set (``autopermalink=False``) will only
    restore the permalink when the new ``autopermalink`` state allows
    regeneration from the reverted title. Capturing the url_node permalinks
    as a virtual field on the page during publish would fix this — left as
    a follow-up.

    Idempotent — safe to call multiple times for the same model.
    """
    if not reversion_available():
        return
    import reversion
    from reversion.revisions import is_registered

    if is_registered(model_cls):
        return
    reversion.register(model_cls, follow=())


def auto_register_page_models() -> None:
    """Register every concrete ``AbstractPage`` descendant with reversion."""
    if not reversion_available():
        return
    from camomilla.models.page import AbstractPage

    for subclass in _all_subclasses(AbstractPage):
        if subclass._meta.abstract:
            continue
        register_page_for_revisions(subclass)


def _all_subclasses(cls):
    seen = set()
    stack = list(cls.__subclasses__())
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen.add(s)
        stack.extend(s.__subclasses__())
    return seen


def _has_translated_lifecycle(model_cls) -> bool:
    """``True`` when the page model has per-language ``publish_at`` columns."""
    from camomilla import settings as camomilla_settings
    from django.core.exceptions import FieldDoesNotExist

    if not camomilla_settings.ENABLE_TRANSLATIONS:
        return False
    try:
        first_lang = camomilla_settings.LANGUAGE_CODES[0]
    except (IndexError, TypeError):
        return False
    try:
        model_cls._meta.get_field(f"publish_at_{first_lang}")
        return True
    except FieldDoesNotExist:
        return False


def resolve_scheduled_pages(model_cls=None):
    """Yield ``(page, language_code)`` pairs whose ``publish_at`` is due.

    Both ``publish_at`` and ``has_draft`` are per-language, so the cron has
    to ask "is any *language* of any page due for publish, and does *that
    language* still carry a pending draft?". For each match we yield the
    language too, so the caller can activate it before running ``publish()``
    — that way the ``published_at_<lang>`` stamp lands in the right column
    and ``_apply_draft_via_serializer`` reads the right ``draft_data_<lang>``.

    The per-language scan uses :func:`activate_languages` and relies on
    ``modeltranslation`` rewriting ``publish_at__lte`` and ``has_draft=True``
    into their ``_<active_lang>`` siblings under the hood, so the filter
    expression itself stays language-agnostic.

    Subclasses not registered with ``modeltranslation`` (e.g. monolingual
    test models) yield once with ``lang=None`` using the base columns.
    """
    from camomilla.models.page import AbstractPage
    from camomilla.utils import activate_languages
    from django.utils import timezone

    models_to_check = [model_cls] if model_cls else list(_all_subclasses(AbstractPage))
    now = timezone.now()

    def _due_qs(subclass):
        return (
            subclass.objects.alive()
            .filter(has_draft=True)
            .filter(publish_at__isnull=False, publish_at__lte=now)
        )

    for subclass in models_to_check:
        if subclass._meta.abstract:
            continue
        if _has_translated_lifecycle(subclass):
            # ``activate_languages`` cycles each language; modeltranslation
            # rewrites ``publish_at`` / ``has_draft`` lookups to the
            # active-language column.
            for lang in activate_languages():
                for page in _due_qs(subclass):
                    yield page, lang
        else:
            for page in _due_qs(subclass):
                yield page, None


__all__ = [
    "reversion_available",
    "register_page_for_revisions",
    "auto_register_page_models",
    "resolve_scheduled_pages",
]
