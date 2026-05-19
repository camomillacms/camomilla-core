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

    Lazy materialisation: if a scheduled content swap is due, the first
    visitor that arrives after ``publish_at`` triggers ``publish()`` and
    renders the freshly-applied content. Subsequent visitors see a normal
    public read. The cron command is the safety net for pages that no one
    ever visits.
    """
    append_slash = getattr(django_settings, "APPEND_SLASH", True)
    redirect_obj = UrlRedirect.find_redirect(request)
    if redirect_obj:
        return redirect_obj.redirect()
    if append_slash and not request.path.endswith("/"):
        q_string = request.META.get("QUERY_STRING", "")
        return redirect(request.path + "/" + ("?" + q_string if q_string else ""))
    if "permalink" in kwargs:
        page = Page.get_or_404(request, bypass_type_check=True)
    elif settings.AUTO_CREATE_HOMEPAGE is False:
        page, _ = Page.get_or_404(permalink="/", bypass_type_check=True)
    else:
        page, _ = Page.get_or_create_homepage()

    # First visitor after publish_at wins the publish; everyone else gets a
    # regular read. Safe under concurrent traffic and no-op when no draft is
    # due.
    page.publish_if_due()

    context = page.get_context(request)
    return render(request, page.get_template_path(request), context)


urlpatterns = [
    path("", fetch, name="camomilla-homepage"),
    path("<path:permalink>", fetch, name="camomilla-permalink"),
]
