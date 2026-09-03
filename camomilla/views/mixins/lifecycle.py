"""Draft / publish / preview actions for any ``AbstractPage`` viewset.

These used to live directly on ``PageViewSet``, which meant only Page had a
draft workflow even though ``Draft`` is generic (``content_type`` +
``object_id``) and every lifecycle method — ``save_draft``, ``publish``,
``schedule``, ``discard_draft``, ``draft_data`` — is defined on
``AbstractPage``. Article, and any project's own page subclass, can have the
same editor workflow by mixing this in.

Nothing here touches Page specifically: every action is ``self.get_object()``
plus a model method, so the mixin is safe on any viewset whose queryset is an
``AbstractPage`` subclass.
"""

from datetime import datetime

from django.shortcuts import render
from django.utils import translation
from django.utils.dateparse import parse_datetime
from django.utils.translation import get_language
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from camomilla.preview import reversion_available
from camomilla.settings import API_TRANSLATION_ACCESSOR


def draft_overlay(page, serialized: dict) -> dict:
    """Merge the active-language Draft on top of ``serialized``.

    Looks up the Draft row for ``(page, active_language)``. When found,
    merges its ``serialized`` payload into the response — translatable
    fields by language key, non-translatable top-level fields directly.

    The merge is language-aware: a flat ``overlay.update(draft)`` would
    clobber the response's full ``translations: {en, it, …}`` map with
    the draft's one-language map, dropping every other language's live
    content from the preview response. We merge by language instead so
    the preview reflects "live IT + drafted EN" correctly.

    The active language is then ALSO flattened onto the top-level keys.
    Every consumer of this payload reads the flat fields — ``page.title``,
    ``page.template_data`` — because that is where the serializer puts the
    active language; ``translations`` is the by-language archive next to
    them. Merging only into ``translations`` left a drafted title visible
    in the JSON and invisible in the rendered preview, which is the whole
    point of the endpoint.
    """
    draft_payload = page.draft_data
    if not draft_payload:
        return serialized
    overlay = dict(serialized)
    draft_translations = draft_payload.get(API_TRANSLATION_ACCESSOR) or {}
    if draft_translations:
        merged = dict(overlay.get(API_TRANSLATION_ACCESSOR) or {})
        for lang, lang_payload in draft_translations.items():
            merged[lang] = {**(merged.get(lang) or {}), **(lang_payload or {})}
        overlay[API_TRANSLATION_ACCESSOR] = merged
        # Only the active language: the flat fields are that language's view.
        for key, value in (draft_translations.get(get_language()) or {}).items():
            overlay[key] = value
    for key, value in draft_payload.items():
        if key != API_TRANSLATION_ACCESSOR:
            overlay[key] = value
    overlay["has_draft"] = True
    # Scheduling state travels with the draft: an editor UI has to distinguish
    # "pending edit" from "pending edit that swaps itself in at 09:00 Monday",
    # and ``scheduled_for`` lives on the Draft row where no serializer sees it.
    overlay["has_scheduled_draft"] = page.has_scheduled_draft
    overlay["draft_scheduled_for"] = page.draft_scheduled_for
    return overlay


class PageLifecycleMixin:
    """``/draft/``, ``/publish/``, ``/preview/`` & friends on a page viewset."""

    def _body_language(self, request):
        """The single language named by the request body, if it names one.

        A ``Draft`` row is keyed by ``(record, language)``, unlike a regular
        PATCH where the body addresses every language at once. Deriving that
        key from ``Accept-Language`` alone made an editor's UI language decide
        where the payload landed — an English-speaking admin editing the IT tab
        staged ``translations: {it: …}`` under an ``en`` row, so the IT preview
        found nothing and publishing IT applied nothing.

        Returns ``None`` when the body names zero or several languages; there
        is nothing to infer from either.
        """
        data = request.data if isinstance(request.data, dict) else {}
        languages = list((data.get(API_TRANSLATION_ACCESSOR) or {}).keys())
        return languages[0] if len(languages) == 1 else None

    def _target_draft_language(self, request):
        """Which language's Draft row this call acts on.

        Explicit wins, then the body, then the request. Same precedence the
        rest of the API follows: ``?language=`` overrides everything, and a
        body that names its language is trusted over ``Accept-Language``.
        ``None`` means "leave the active language alone".
        """
        if getattr(self, "language_explicit", False):
            return None  # ``?language=`` is already the active language.
        return self._body_language(request)

    @action(detail=True, methods=["patch", "put"], url_path="draft")
    def draft(self, request, pk=None):
        """Save the request body as a language's pending Draft.

        The body shape mirrors a regular PATCH on the page — the publish
        serializer will replay it later. Which language's Draft row it lands
        in follows :meth:`_target_draft_language`: ``?language=`` if given, else the
        language the body names, else the request's.

        A body that names *several* languages still lands wholesale in the
        active language's row, and publishing that row applies all of them —
        pass ``?language=`` when that is what you mean.
        """
        page = self.get_object()
        merge = request.method.lower() == "patch"
        language = self._target_draft_language(request) or translation.get_language()
        with translation.override(language):
            page.save_draft(request.data, merge=merge)
            return Response(self.get_serializer(page).data)

    @action(detail=True, methods=["post"], url_path="discard-draft")
    def discard_draft(self, request, pk=None):
        page = self.get_object()
        page.discard_draft()
        return Response(self.get_serializer(page).data)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        page = self.get_object()
        comment = (
            request.data.get("comment", "") if isinstance(request.data, dict) else ""
        )
        page.publish(comment=comment)
        return Response(self.get_serializer(page).data)

    @action(detail=True, methods=["post"], url_path="schedule")
    def schedule(self, request, pk=None):
        """Schedule the next publish moment.

        Body: ``{"publish_at": "<ISO 8601 datetime>"}``.

        Semantics depend on the page's current state (see
        :meth:`AbstractPage.schedule`): for a never-public language the
        moment becomes the first-appearance ``published_at``; for a
        currently-public language the moment is attached to the pending
        Draft (must be saved first via ``/draft/``).
        """
        page = self.get_object()
        body = request.data if isinstance(request.data, dict) else {}
        raw = body.get("publish_at")
        if not raw:
            return Response(
                {"publish_at": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dt = parse_datetime(raw) if isinstance(raw, str) else raw
        if not isinstance(dt, datetime):
            return Response(
                {"publish_at": "Invalid datetime."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        page.schedule(dt)
        return Response(self.get_serializer(page).data)

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        """Author/admin-only JSON preview: live page + draft overlay.

        Permission to call this action comes from the viewset's regular
        model permissions — only authenticated users with edit rights see it.
        """
        page = self.get_object()
        data = self.get_serializer(page).data
        return Response(draft_overlay(page, data))

    @action(detail=True, methods=["get"], url_path="render")
    def render_preview(self, request, pk=None):
        """Author/admin-only HTML preview: render the page template with
        the draft payload exposed in the template context."""
        page = self.get_object()
        context = page.get_context(request)
        draft_payload = page.draft_data
        if draft_payload:
            context["draft_data"] = draft_payload
        return render(request, page.get_template_path(request), context)

    @action(detail=True, methods=["get"], url_path="revisions")
    def revisions(self, request, pk=None):
        if not reversion_available():
            return Response(
                {"detail": "django-reversion not installed"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        page = self.get_object()
        versions = page.list_revisions()
        data = [
            {
                "id": v.pk,
                "revision_id": v.revision_id,
                "date_created": v.revision.date_created,
                "comment": v.revision.get_comment(),
                "user": getattr(v.revision.user, "username", None),
            }
            for v in versions
        ]
        return Response(data)

    @action(detail=True, methods=["post"], url_path=r"revert/(?P<version_id>\d+)")
    def revert(self, request, pk=None, version_id=None):
        if not reversion_available():
            return Response(
                {"detail": "django-reversion not installed"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        page = self.get_object()
        page.revert_to_revision(int(version_id))
        return Response(self.get_serializer(page).data)
