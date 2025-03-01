from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from camomilla.models import Media, MediaFolder
from camomilla.parsers import MultipartJsonParser
from camomilla.permissions import CamomillaBasePermissions
from camomilla.serializers import (
    MediaFolderSerializer,
    MediaListSerializer,
    MediaSerializer,
)
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import (
    BulkDeleteMixin,
    GetUserLanguageMixin,
    TrigramSearchMixin,
)


class ParseMimeMixin(object):
    def parse_filter(self, filter):
        filter_name, value = filter.split("=")
        if filter_name == "mime_type":
            if value == "*/*":
                return "mime_type__isnull", False
            elif value.endswith("/*"):
                return "mime_type__startswith", value.split("/")[0]
        return filter_name, super().parse_qs_value(value)


class MediaFolderViewSet(
    GetUserLanguageMixin, ParseMimeMixin, TrigramSearchMixin, BaseModelViewset
):
    model = MediaFolder
    serializer_class = MediaFolderSerializer
    permission_classes = (CamomillaBasePermissions,)
    items_per_page = 18
    search_fields = ["title", "alt_text", "file"]

    def get_queryset(self):
        return self.model.objects.all()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "action": "list"}

    def get_mixed_response(self, request, *args, **kwargs):
        search = self.request.GET.get("search", None)
        all = self.request.GET.get("all", "false").lower() == "true"
        updir = None if all else kwargs.get("pk", None)
        if not search and all:
            self.search_fields = []

        parent_folder = MediaFolderSerializer(
            self.model.objects.filter(pk=updir).first()
        ).data
        folder_queryset = self.model.objects.filter(updir__pk=updir)
        media_queryset = Media.objects.filter(**({} if all else {"folder__pk": updir}))

        folder_data = MediaFolderSerializer(
            folder_queryset, many=True, context={"request": request}
        ).data
        media_data = self.format_output(
            *self.handle_pagination_stack(media_queryset),
            SerializerClass=MediaListSerializer,
        )
        return {
            "folders": folder_data,
            "media": media_data,
            "parent_folder": parent_folder,
        }

    def list(self, request, *args, **kwargs):
        return Response(self.get_mixed_response(request, *args, **kwargs))

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_mixed_response(request, *args, **kwargs))


class MediaViewSet(
    GetUserLanguageMixin,
    BulkDeleteMixin,
    ParseMimeMixin,
    TrigramSearchMixin,
    BaseModelViewset,
):
    queryset = Media.objects.all()
    serializer_class = MediaSerializer
    permission_classes = (CamomillaBasePermissions,)
    model = Media
    parser_classes = [MultipartJsonParser, JSONParser]
