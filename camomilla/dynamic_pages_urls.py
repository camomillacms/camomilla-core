from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import path

from camomilla import settings
from django.conf import settings as django_settings
from .models import Page, UrlRedirect


def fetch(request, *args, **kwargs):
    """Public HTML renderer for a Camomilla page.

    Always serves the *public* state of the page. Non-public pages 404 — there
    is no ``?preview=`` flag and no staff-bypass: editor previews are served
    exclusively from the authenticated ``/api/.../pages/{id}/render/`` action.

    Lazy materialisation: if a Draft with ``scheduled_for`` in the past
    is attached to this page in the active language, the first visitor
    triggers ``publish()`` and renders the freshly-applied content.
    Subsequent visitors see a normal public read. The cron command is the
    safety net for pages that no one ever visits.
    """
    append_slash = getattr(django_settings, "APPEND_SLASH", True)
    redirect_obj = UrlRedirect.find_redirect(request)
    if redirect_obj:
        return redirect_obj.redirect()
    if append_slash and not request.path.endswith("/"):
        q_string = request.META.get("QUERY_STRING", "")
        return redirect(request.path + "/" + ("?" + q_string if q_string else ""))
    if "permalink" in kwargs:
        # ``get_or_404`` filters through ``Page.get``, which raises when
        # ``is_public`` is False — trashed, draft, and scheduled rows 404 here.
        page = Page.get_or_404(request, bypass_type_check=True)
    elif settings.AUTO_CREATE_HOMEPAGE is False:
        page = Page.get_or_404(request, permalink="/", bypass_type_check=True)
    else:
        # Auto-created homepages are stamped as public on creation, but an
        # existing homepage that was later trashed (or whose ``published_at``
        # was cleared) must NOT be served. The ``is_public`` check below
        # enforces that — and runs after ``publish_if_due()`` so a Draft-based
        # first-publish can still promote the homepage on the way in.
        page, _ = Page.get_or_create_homepage()

    # First visitor whose active language has a due Draft wins the publish;
    # everyone else gets a regular read. Safe under concurrent traffic
    # and no-op when no Draft is due.
    page.publish_if_due()

    if not page.is_public:
        raise Http404("Page is not public")

    context = page.get_context(request)
    return render(request, page.get_template_path(request), context)


urlpatterns = [
    path("", fetch, name="camomilla-homepage"),
    path("<path:permalink>", fetch, name="camomilla-permalink"),
]
