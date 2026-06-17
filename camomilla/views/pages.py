from datetime import datetime

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime
from django.utils.translation.trans_real import activate as activate_language
from rest_framework import permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from camomilla.models import Page
from camomilla.models.page import UrlNode, UrlRedirect
from camomilla.preview import reversion_available
from camomilla.serializers import PageSerializer
from camomilla.serializers.page import RouteSerializer
from camomilla.settings import API_TRANSLATION_ACCESSOR, PAGE_ROUTER_CACHE
from camomilla.utils.translation import url_lang_decompose
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import staff_excluded_cache
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin


def _draft_overlay(page, serialized: dict) -> dict:
    """Merge the active-language Draft on top of ``serialized``.

    Looks up the Draft row for ``(page, active_language)``. When found,
    merges its ``serialized`` payload into the response — translatable
    fields by language key, non-translatable top-level fields directly.

    The merge is language-aware: a flat ``overlay.update(draft)`` would
    clobber the response's full ``translations: {en, it, …}`` map with
    the draft's one-language map, dropping every other language's live
    content from the preview response. We merge by language instead so
    the preview reflects "live IT + drafted EN" correctly.
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
    for key, value in draft_payload.items():
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
        """Save the request body as the active language's pending Draft.

        The body shape mirrors a regular PATCH on the page — the publish
        serializer will replay it later. Cross-language scoping is no
        longer required at the view layer: the Draft model writes to the
        active language by construction, so a payload that includes both
        ``translations[en]`` and ``translations[it]`` lands wholesale in
        the active language's Draft row, and an EN publish only applies
        what that row carries.
        """
        page = self.get_object()
        merge = request.method.lower() == "patch"
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
        return Response(_draft_overlay(page, data))

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


def _eager_load_routing_chain(node: UrlNode) -> None:
    """Eager-load the resolved page's ancestor chain in one query.

    The router serializes ``node.page`` at a deep nesting level, which walks
    ``parent_page`` for both the breadcrumbs and the nested ``parent_page``
    representation — an ``O(depth)`` N+1 (one ``url_node`` + one ``page`` query
    per ancestor) when the chain isn't eager-loaded. ``with_page()`` already
    cached ``node.page`` but not its ancestry, and the chain can't be folded
    into the resolve query itself: that join would have to span *every* concrete
    page model at once, blowing past the column limit. So re-fetch the single
    resolved page with its routing chain (``parent_page__…__url_node``) and
    re-prime the node's reverse cache, making the whole walk cache-resident at
    the cost of one extra query. Root pages (no ``parent_page``) have nothing to
    walk and are skipped, so shallow trees pay nothing.
    """
    page = node.page
    if page is None or not getattr(page, "parent_page_id", None):
        return
    hydrated = type(page).objects.with_urls().get(pk=page.pk)
    setattr(node, node.related_name, hydrated)


def _resolve_route_request(permalink: str) -> tuple[UrlNode, dict | None]:
    """Resolve a request permalink to its ``UrlNode`` and, when the request
    form differs from the canonical form, a ``{redirect, status: 301}``
    descriptor.

    Shared between the public router and the authenticated preview router.
    Activates the language detected on the path so downstream serializer /
    template code reads the right per-language columns, and computes the
    canonical URL against the FULL requested path — a single rule catches
    trailing-slash, bare-lang-prefix, and lang-sub-path-no-slash mismatches
    at once.

    Raises ``Http404`` when no ``UrlNode`` matches. Public-vs-preview
    policy (``is_public`` gate, ``publish_if_due`` materialisation, draft
    overlay) is the caller's responsibility.
    """
    decomposition = url_lang_decompose(permalink)
    activate_language(decomposition["language"])
    decomposed_permalink = decomposition["permalink"]
    # ``UrlNode.permalink`` is stored without a trailing slash (except
    # the homepage ``"/"``); look up against the stripped form so both
    # ``/about`` and ``/about/`` resolve to the same row.
    lookup_path = (
        decomposed_permalink
        if decomposed_permalink == "/"
        else decomposed_permalink.rstrip("/")
    )
    node: UrlNode = get_object_or_404(
        UrlNode.objects.with_page(), permalink=lookup_path
    )
    _eager_load_routing_chain(node)
    full_requested_path = (
        permalink if permalink.startswith("/") else "/" + permalink
    )
    canonical_url = UrlNode.reverse_url(lookup_path) or full_requested_path
    canonical = (
        {"redirect": canonical_url, "status": 301}
        if canonical_url != full_requested_path
        else None
    )
    return node, canonical


@api_view(["GET"])
@staff_excluded_cache(PAGE_ROUTER_CACHE)
@permission_classes(
    [
        permissions.AllowAny,
    ]
)
def pages_router(request, permalink=""):
    """Public route resolver. Always serves *public* state.

    Lazy materialisation: if a Draft is due, the first visitor — through
    *any* public channel, API or HTML — wins the publish. The cron
    command is the safety net for pages that nobody ever visits. Mirrors
    the HTML route in :mod:`camomilla.dynamic_pages_urls` so an API-only
    frontend and a server-rendered template stay in lockstep on lifecycle
    transitions.

    Editor previews are served by ``pages_router_preview`` (same shape,
    auth-required, bypasses ``is_public`` and overlays the Draft) and by
    ``PageViewSet.preview`` / ``PageViewSet.render_preview`` (page-id
    routed, used by the admin Draft Inspector).
    """
    redirect_obj = UrlRedirect.find_redirect_from_url(f"/{permalink}")
    if redirect_obj:
        redirected = redirect_obj.redirect()
        return Response({"redirect": redirected.url, "status": redirected.status_code})

    node, canonical = _resolve_route_request(permalink)
    page = node.page

    # First public read after the Draft becomes due wins the publish;
    # re-fetch the node so the response reflects the freshly-applied
    # state (the node's annotated fields — is_public, status — were
    # computed before the row was flipped).
    if page.publish_if_due():
        node = UrlNode.objects.with_page().get(pk=node.pk)
        _eager_load_routing_chain(node)

    # ``is_public`` MUST be checked before honoring the canonical-form
    # redirect, otherwise the descriptor leaks the existence of non-public
    # rows: an attacker probing hidden URLs would get a 301 (page exists,
    # non-canonical URL) instead of a 404. Runs *after* ``publish_if_due()``
    # so a never-public page with a due Draft is allowed to flip to public
    # on the way in.
    if not page.is_public:
        raise Http404("Page is not public")

    if canonical is not None:
        return Response(canonical)

    data = RouteSerializer(node, context={"request": request}).data
    return Response(data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def pages_router_preview(request, permalink=""):
    """Authenticated mirror of :func:`pages_router` for editor previews.

    Returns the same ``RouteSerializer``-shaped payload as ``pages_router``
    but with two differences:

    * The ``is_public`` gate is bypassed — trashed, draft, and scheduled
      rows return their content here so editors can preview every state.
    * The active-language Draft is overlaid via ``_draft_overlay`` and the
      response carries ``has_draft: true`` when one exists.

    Crucially does **not** call :meth:`AbstractPage.publish_if_due`. A
    preview must show the *current* pending state — running the lazy
    publish would consume the Draft as a side-effect of looking at it,
    which is exactly the wrong semantics for a preview.

    Lookup by permalink is intentionally single-shot here so external
    rendering frontends (e.g. the astro integration) don't have to do a
    list-then-detail round-trip to resolve a page by URL for preview.
    """
    node, canonical = _resolve_route_request(permalink)
    if canonical is not None:
        return Response(canonical)
    data = RouteSerializer(node, context={"request": request}).data
    return Response(_draft_overlay(node.page, data))
