from ..mixins import (
    OptimViewMixin,
    PaginateStackMixin,
    OrderingMixin,
    CamomillaBasePermissionMixin,
)
from camomilla.serializers.mixins import TranslationsMixin
from camomilla.utils.translation import plain_to_nest
from rest_framework import viewsets
from rest_framework.metadata import SimpleMetadata
from structured.contrib.restframework import StructuredJSONField


base_viewset_classes = [
    CamomillaBasePermissionMixin,
    OptimViewMixin,
    OrderingMixin,
    PaginateStackMixin,
    viewsets.ModelViewSet,
]


class BaseViewMetadata(SimpleMetadata):

    def get_field_info(self, field):
        field_info = super().get_field_info(field)
        if isinstance(field, StructuredJSONField):
            field_info["schema"] = field.schema.json_schema()
            field_info["type"] = "structured-json"
        return field_info

    def get_serializer_info(self, serializer):
        info = super().get_serializer_info(serializer)
        if isinstance(serializer, TranslationsMixin) and serializer.is_translatable:
            info.update(plain_to_nest(info, serializer.translation_fields))
        return info


class BaseModelViewset(*base_viewset_classes):
    metadata_class = BaseViewMetadata
