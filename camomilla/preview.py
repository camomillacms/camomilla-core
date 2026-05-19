"""
Page drafting, scheduling, and revision helpers.

Drafts live in :class:`camomilla.models.draft.Draft` — one row per
``(page, language)`` carries the staged payload and (optional)
``scheduled_for`` moment. The live page row is always the published
state; pending edits accumulate as Draft rows until an editor publishes,
schedules, or discards them.

Preview is **author/admin only** and exposed through the dedicated
``/pages/{id}/preview/`` and ``/pages/{id}/render/`` viewset actions, which
inherit DRF model permissions. There is no public preview path: the public
router serves only published content (with the read-time scheduled-swap
materialisation applied automatically when a Draft is due).

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


def resolve_scheduled_pages():
    """Yield ``(page, language_code)`` pairs whose draft is due to publish.

    The cron worklist is :meth:`Draft.objects.due_now`. Iterating Drafts
    directly (instead of cycling pages × languages) is both faster and
    correct by construction — ``Draft.language`` carries the language code
    explicitly, so there's no need to probe per-language columns.

    The caller activates the yielded language before invoking
    ``page.publish()`` so the per-language ``published_at_<lang>`` stamp
    lands on the right column.
    """
    from camomilla.models.draft import Draft, NO_LANGUAGE

    for draft in Draft.objects.due_now().select_related("content_type"):
        page = draft.content_object
        if page is None:
            # Orphaned draft (page was deleted out from under it). Skip;
            # cron will leave it for cleanup.
            continue
        yield page, (draft.language or None) if draft.language != NO_LANGUAGE else None


__all__ = [
    "reversion_available",
    "register_page_for_revisions",
    "auto_register_page_models",
    "resolve_scheduled_pages",
]
