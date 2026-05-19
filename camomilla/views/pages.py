from datetime import datetime

from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime
from django.utils.translation.trans_real import activate as activate_language
from rest_framework import permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from django.utils.translation import get_language

from camomilla.models import Page
from camomilla.models.page import UrlNode, UrlRedirect
from camomilla.preview import reversion_available
from camomilla.serializers import PageSerializer
from camomilla.serializers.page import RouteSerializer
from camomilla.settings import API_TRANSLATION_ACCESSOR, PAGE_ROUTER_CACHE
from camomilla.utils import get_nofallbacks
from camomilla.utils.translation import url_lang_decompose
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import staff_excluded_cache
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin


def _scope_draft_to_active_language(data):
    """Trim a ``/draft/`` body to the active language's content only.

    Backoffice edit-forms typically PATCH the full page object back to the
    server — including BOTH languages under ``translations``. With per-
    language ``draft_data``, the whole body would land in the active
    language's column and a later publish would carry the OTHER language's
    translations along for the ride (cross-language leak).

    This helper keeps only ``translations[<active_lang>]`` (dropping any
    other language entries) and leaves non-translatable top-level fields
    (``ordering``, ``parent_page``, ``template``, …) untouched. Those are
    globally-shared columns — whichever publish runs next carries forward
    whatever shared state was drafted alongside it (last-write-wins).

    Non-dict bodies and bodies without a ``translations`` accessor pass
    through unchanged.
    """
    if not isinstance(data, dict):
        return data
    if API_TRANSLATION_ACCESSOR not in data:
        return data
    translations = data.get(API_TRANSLATION_ACCESSOR) or {}
    if not isinstance(translations, dict):
        return data
    active = get_language()
    scoped = dict(data)
    scoped[API_TRANSLATION_ACCESSOR] = (
        {active: translations[active]} if active in translations else {}
    )
    return scoped


def _draft_overlay(page, serialized: dict) -> dict:
    """Merge the active-language ``draft_data`` on top of ``serialized``.

    Two reads of ``draft_data`` are language-scoped:

    * Source — :func:`get_nofallbacks` picks the active language's column,
      so EN's preview never surfaces an IT-only draft.
    * Shape — the stored draft carries ``translations[<active>]`` plus
      non-translatable top-level fields (the view trims it that way at
      write time, see :func:`_scope_draft_to_active_language`).

    The overlay therefore has to *merge* the ``translations`` bundle by
    language key rather than replacing it: a flat ``overlay.update(draft)``
    would clobber the response's full ``{en, it, …}`` map with the draft's
    one-language map, dropping every other language's live content from
    the preview response.
    """
    draft = get_nofallbacks(page, "draft_data")
    if not draft:
        return serialized
    overlay = dict(serialized)
    draft_translations = draft.get(API_TRANSLATION_ACCESSOR) or {}
    if draft_translations:
        merged = dict(overlay.get(API_TRANSLATION_ACCESSOR) or {})
        for lang, lang_payload in draft_translations.items():
            merged[lang] = {**(merged.get(lang) or {}), **(lang_payload or {})}
        overlay[API_TRANSLATION_ACCESSOR] = merged
    for key, value in draft.items():
        if key != API_TRANSLATION_ACCESSOR:
            overlay[key] = value
    overlay["has_draft"] = True
    return overlay


class PageViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    model = Page

    @action(detail=True, methods=["patch", "put"], url_path="draft")
    def draft(self, request, pk=None):
        page = self.get_object()
        merge = request.method.lower() == "patch"
        page.save_draft(_scope_draft_to_active_language(request.data), merge=merge)
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
        """Schedule the next publish action at ``publish_at``.

        Body: ``{"publish_at": "<ISO 8601 datetime>"}``.
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
        return Response(_draft_overlay(page, data))

    @action(detail=True, methods=["get"], url_path="render")
    def render_preview(self, request, pk=None):
        """Author/admin-only HTML preview: render the page template with
        the draft overlay applied to the template context."""
        page = self.get_object()
        context = page.get_context(request)
        draft = get_nofallbacks(page, "draft_data")
        if draft:
            context["draft_data"] = draft
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


@api_view(["GET"])
@staff_excluded_cache(PAGE_ROUTER_CACHE)
@permission_classes(
    [
        permissions.AllowAny,
    ]
)
def pages_router(request, permalink=""):
    """Public route resolver. Always serves *public* state.

    Lazy materialisation: if a scheduled content swap is due, the first
    visitor — through *any* public channel, API or HTML — wins the publish.
    The cron command is the safety net for pages that nobody ever visits.
    Mirrors the HTML route in :mod:`camomilla.dynamic_pages_urls` so an
    API-only frontend and a server-rendered template stay in lockstep on
    lifecycle transitions.

    Editor previews are served exclusively by ``PageViewSet.preview`` and
    ``PageViewSet.render_preview``, both of which require authentication.
    """
    redirect_obj = UrlRedirect.find_redirect_from_url(f"/{permalink}")
    if redirect_obj:
        redirected = redirect_obj.redirect()
        return Response({"redirect": redirected.url, "status": redirected.status_code})
    url_decomposition = url_lang_decompose(permalink)
    if not url_decomposition["permalink"].startswith("/"):
        url_decomposition["permalink"] = f"/{url_decomposition['permalink']}"
    activate_language(url_decomposition["language"])
    node: UrlNode = get_object_or_404(UrlNode, permalink=url_decomposition["permalink"])
    page = node.page

    # First public read after publish_at wins the publish; re-fetch the
    # node so the response reflects the freshly-applied state (the node's
    # annotated fields — is_public, has_draft, status — were computed
    # before the row was flipped).
    if page.publish_if_due():
        node = UrlNode.objects.get(pk=node.pk)
    data = RouteSerializer(node, context={"request": request}).data
    return Response(data)
