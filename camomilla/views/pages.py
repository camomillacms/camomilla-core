import hashlib
import json

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation.trans_real import activate as activate_language
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from camomilla.models import Page
from camomilla.models.page import UrlNode, UrlRedirect
from camomilla.models.site import SiteEpoch
from camomilla.serializers import PageSerializer
from camomilla.serializers.page import RouteSerializer
from camomilla.settings import PAGE_ROUTER_CACHE
from camomilla.utils.pages import public_path
from camomilla.utils.translation import (
    activate_languages,
    get_nofallbacks,
    url_lang_decompose,
)
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import staff_excluded_cache
from camomilla.views.mixins import (
    BulkDeleteMixin,
    PageLifecycleMixin,
    draft_overlay,
)


class PageViewSet(PageLifecycleMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    model = Page


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
    node: UrlNode = get_object_or_404(UrlNode, permalink=lookup_path)
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
        node = UrlNode.objects.get(pk=node.pk)

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
    * The active-language Draft is overlaid via ``draft_overlay`` and the
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
    return Response(draft_overlay(node.page, data))


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def pages_router_changes(request):
    nodes = list(UrlNode.objects.prefetch_pages())
    urls = []
    for language_code in activate_languages():
        for node in nodes:
            try:
                page = node.page
            except ObjectDoesNotExist:
                continue  # orphaned UrlNode (no page)
            page.url_node = node
            if not page.is_public:
                continue
            permalink = get_nofallbacks(node, "permalink")
            if not permalink:
                continue
            payload = RouteSerializer(node, context={"request": request}).data
            blob = json.dumps(payload, sort_keys=True, default=str)
            urls.append(
                {
                    "path": public_path(language_code, permalink),
                    "permalink": permalink,
                    "language_code": language_code,
                    "hash": hashlib.sha1(blob.encode("utf-8")).hexdigest(),
                }
            )

    redirects = [
        {
            "from": public_path(r.language_code, r.from_url),
            "to": r.redirect_to,
            "status": 301 if r.permanent else 302,
        }
        for r in UrlRedirect.objects.all()
    ]

    return Response(
        {
            "server_time": timezone.now(),
            "epoch": SiteEpoch.current(),
            "urls": urls,
            "redirects": redirects,
        }
    )


@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def pages_router_publish_due(request):
    """Apply any due scheduled Drafts, then report how many were published.

    On a static/CDN deploy nobody hits the SSR route, so the lazy
    ``publish_if_due`` that normally fires on first read never runs. The
    incremental build calls this first (step 0) so scheduled content that has
    come due is materialised before the manifest is computed. Staff-only
    (``IsAdminUser``) — satisfied by a session cookie or a DRF token, so a
    headless build authenticates with ``Authorization: Token <...>``.

    Idempotent: re-running with nothing due publishes zero and is a no-op.
    Mirrors the ``camomilla_publish_scheduled`` management command (both walk
    the same :func:`resolve_scheduled_pages`) for the manual-trigger flow
    that has no cron.
    """
    from camomilla.preview import resolve_scheduled_pages

    published = 0
    for page, lang in resolve_scheduled_pages():
        original = get_language()
        try:
            if lang:
                activate_language(lang)
            page.publish(comment="Scheduled publish (static build)")
            published += 1
        finally:
            if original:
                activate_language(original)
    return Response({"published": published})
