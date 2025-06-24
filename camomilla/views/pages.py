from camomilla.models import Page
from camomilla.models.page import UrlNode, UrlRedirect
from camomilla.permissions import CamomillaBasePermissions
from camomilla.serializers import PageSerializer
from camomilla.serializers.page import RouteSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import active_lang
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404


class PageViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Page.objects.all()
    serializer_class = PageSerializer
    permission_classes = (CamomillaBasePermissions,)
    model = Page


@active_lang()
@api_view(["GET"])
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
    node: UrlNode = get_object_or_404(UrlNode, permalink=f"/{permalink}")
    return Response(RouteSerializer(node, context={"request": request}).data)
