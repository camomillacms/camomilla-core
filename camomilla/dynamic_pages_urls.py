from django.shortcuts import redirect, render
from django.urls import path

from camomilla import settings
from django.conf import settings as django_settings
from .models import Page, UrlRedirect


def fetch(request, *args, **kwargs):
    can_preview = request.user.is_staff or settings.DEBUG
    preview = can_preview and request.GET.get("preview", False)
    append_slash = getattr(django_settings, "APPEND_SLASH", True)
    redirect_obj = UrlRedirect.find_redirect(request)
    if redirect_obj:
        return redirect_obj.redirect()
    if append_slash and not request.path.endswith("/"):
        q_string = request.META.get("QUERY_STRING", "")
        return redirect(request.path + "/" + ("?" + q_string if q_string else ""))
    if "permalink" in kwargs:
        page = Page.get_or_404(
            request, bypass_public_check=preview, bypass_type_check=True
        )
    elif settings.AUTO_CREATE_HOMEPAGE is False:
        page, _ = Page.get_or_404(permalink="/", bypass_type_check=True)
    else:
        page, _ = Page.get_or_create_homepage()
    return render(request, page.get_template_path(request), page.get_context(request))


urlpatterns = [
    path("", fetch, name="camomilla-homepage"),
    path("<path:permalink>", fetch, name="camomilla-permalink"),
]
