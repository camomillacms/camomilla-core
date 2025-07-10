from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response

from camomilla.models import AbstractPage, Menu
from camomilla.models.page import UrlNode
from camomilla.permissions import CamomillaBasePermissions
from camomilla.serializers import ContentTypeSerializer, MenuSerializer
from camomilla.serializers.page import UrlNodeSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.decorators import active_lang


class MenuViewSet(BaseModelViewset):
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = (CamomillaBasePermissions,)
    model = Menu

    lookup_field = "key"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
            % (self.__class__.__name__, lookup_url_kwarg)
        )
        filter = Q(**{self.lookup_field: self.kwargs[lookup_url_kwarg]})
        if (
            isinstance(self.kwargs[lookup_url_kwarg], str)
            and self.kwargs[lookup_url_kwarg].isnumeric()
            or isinstance(self.kwargs[lookup_url_kwarg], int)
        ):
            filter |= Q(pk=self.kwargs[lookup_url_kwarg])

        obj = get_object_or_404(queryset, filter)
        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    @action(detail=False, methods=["get"], url_path="page_types")
    def page_types(self, request, *args, **kwargs):
        return Response(
            ContentTypeSerializer(
                [
                    model
                    for model in ContentType.objects.all()
                    if model.model_class()
                    and issubclass(model.model_class(), AbstractPage)
                ],
                many=True,
            ).data
        )

    @action(detail=False, methods=["get"], url_path=r"page_types/(?P<content_id>\w+)")
    def page_type_instances(self, request, content_id, *args, **kwargs):
        content_type = ContentType.objects.filter(pk=content_id).first()
        if not content_type or not issubclass(content_type.model_class(), AbstractPage):
            raise Http404("No object matches the given query.")
        return Response(
            [
                {
                    "id": obj.pk,
                    "name": str(obj),
                    "url_node_id": obj.url_node.pk,
                    "model": f"{content_type.app_label}.{content_type.model}",
                }
                for obj in content_type.model_class().objects.exclude(
                    url_node__isnull=True
                )
            ]
        )

    @active_lang()
    @action(detail=False, methods=["get"], url_path="search_urlnode")
    def search_urlnode(self, request, *args, **kwargs):
        url_node = request.GET.get("q", "")
        qs = UrlNode.objects.filter(permalink__icontains=url_node).order_by("permalink")
        return Response(UrlNodeSerializer(qs, many=True).data)
