from ..mixins import (
    OptimViewMixin,
    PaginateStackMixin,
    OrderingMixin,
    CamomillaBasePermissionMixin,
)
from camomilla.serializers.mixins import TranslationsMixin
from camomilla.openapi.schema import FormAutoSchema
from camomilla.settings import API_TRANSLATION_ACCESSOR
from camomilla.utils.translation import get_lang_info, plain_to_nest
from ..mixins.language import resolve_request_language
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
            # Same accessor the serializer reads on write (TranslationsMixin
            # passes API_TRANSLATION_ACCESSOR to nest_to_plain), otherwise this
            # block advertises "translations" on a project that customised the
            # setting — the exact hardcoding lang_info.accessor exists to prevent.
            info.update(
                plain_to_nest(
                    info, serializer.translation_fields, API_TRANSLATION_ACCESSOR
                )
            )
        return info

    def determine_metadata(self, request, view):
        """
        Publish `lang_info` and a flat, form-oriented `schema` on OPTIONS.

        OPTIONS is the authoritative source for both: they describe the model
        rather than an instance, they are unaffected by a serializer that lists
        Meta.fields explicitly, and they are the only thing a "create new" form
        can consult — there is no record to retrieve yet.
        """
        metadata = super().determine_metadata(request, view)

        serializer = self._get_serializer(view)
        model = getattr(view, "model", None) or getattr(
            getattr(view, "queryset", None), "model", None
        )

        if model is not None:
            metadata["lang_info"] = get_lang_info(
                model,
                translation_fields=getattr(serializer, "translation_fields", None),
            )
            # Where a client must WRITE per-language values. Published rather
            # than assumed: the accessor is configurable, and a client that
            # hardcoded "translations" would write to a key nest_to_plain never
            # reads — dropping every translation on save, undetectably.
            metadata["lang_info"]["accessor"] = API_TRANSLATION_ACCESSOR

        if serializer is not None:
            metadata["schema"] = FormAutoSchema().map_serializer(serializer)

        return metadata

    def _get_serializer(self, view):
        """
        The view's serializer, or None.

        Its ``translation_fields`` is a superset of the modeltranslation registry
        — page serializers append ``permalink`` — so the registry alone would
        report permalink as untranslatable and a client's edits to it would be
        silently dropped.
        """
        try:
            return view.get_serializer()
        except Exception:
            # Metadata must never be the thing that 500s an OPTIONS call.
            return None


class BaseModelViewset(*base_viewset_classes):
    metadata_class = BaseViewMetadata

    def initialize_request(self, request, *args, **kwargs):
        """Activate the request's language before anything reads a column.

        Here rather than on each viewset so ``?language=`` is a property of the
        whole API — project models registered through ``model_api`` included,
        which previously ignored it and could only be addressed through
        ``Accept-Language``. Called as a function, not inherited from
        ``GetUserLanguageMixin``: viewsets that list that mixin themselves are a
        documented pattern, and having it on both sides is an inconsistent MRO.
        """
        resolve_request_language(self, request)
        return super().initialize_request(request, *args, **kwargs)
