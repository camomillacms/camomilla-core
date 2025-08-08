from camomilla.models import Page
from camomilla.models.page import UrlNode, UrlRedirect
from camomilla.serializers import PageSerializer
from camomilla.serializers.page import RouteSerializer
from camomilla.utils.translation import url_lang_decompose
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import staff_excluded_cache
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.utils.translation.trans_real import activate as activate_language
from django.shortcuts import get_object_or_404
from camomilla.settings import PAGE_ROUTER_CACHE


class PageViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    model = Page


@api_view(["GET"])
@staff_excluded_cache(PAGE_ROUTER_CACHE)
@permission_classes(
    [
        permissions.AllowAny,
    ]
)
def pages_router(request, permalink=""):
    redirect = UrlRedirect.find_redirect_from_url(f"/{permalink}")
    if redirect:
        redirect = redirect.redirect()
        return Response({"redirect": redirect.url, "status": redirect.status_code})
    url_decomposition = url_lang_decompose(permalink)
    if not url_decomposition["permalink"].startswith("/"):
        url_decomposition["permalink"] = f"/{url_decomposition['permalink']}"
    activate_language(url_decomposition["language"])
    node: UrlNode = get_object_or_404(UrlNode, permalink=url_decomposition["permalink"])
    return Response(RouteSerializer(node, context={"request": request}).data)
