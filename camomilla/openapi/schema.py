from rest_framework.schemas.openapi import (
    SchemaGenerator as DRFSchemaGenerator,
    AutoSchema as DRFAutoSchema,
)
from camomilla.utils.getters import find_and_replace_dict
from camomilla.utils.translation import plain_to_nest
from camomilla.settings import API_TRANSLATION_ACCESSOR
from camomilla.serializers.mixins import TranslationsMixin
from structured.contrib.restframework import StructuredJSONField


class AutoSchema(DRFAutoSchema):
    extra_components = {}

    def map_serializer(self, serializer):
        schema = super(AutoSchema, self).map_serializer(serializer)
        if isinstance(serializer, TranslationsMixin) and serializer.is_translatable:
            schema = plain_to_nest(schema["properties"], serializer.translation_fields)
            schema[API_TRANSLATION_ACCESSOR] = {
                "type": "object",
                "properties": {
                    k: {"type": "object", "properties": v}
                    for k, v in schema[API_TRANSLATION_ACCESSOR].items()
                },
            }
        return schema

    def get_components(self, path, method):
        components = super().get_components(path, method)
        if len(self.extra_components.keys()) > 0:
            components = {**(components or {}), **self.extra_components}
        return components

    def map_field(self, field):
        if isinstance(field, StructuredJSONField):

            def replace(key, value):
                if isinstance(value, str) and value.startswith("#/definitions"):
                    return value.replace("#/definitions", "#/components/schemas")
                return value

            self.extra_components.update(
                **find_and_replace_dict(
                    field.json_schema.pop("definitions", {}), replace
                )
            )

            return find_and_replace_dict(field.json_schema, replace)
        return super().map_field(field)


class SchemaGenerator(DRFSchemaGenerator):
    def create_view(self, callback, method, request=None):
        view = super(SchemaGenerator, self).create_view(callback, method, request)
        view.schema = AutoSchema()
        if (
            not hasattr(view, "get_queryset")
            and getattr(view, "queryset", None) is None
        ):
            attname = "permission_classes"
            cname = "DjangoModelPermissions"
            setattr(
                view,
                attname,
                [p for p in getattr(view, attname, []) if cname not in p.__name__],
            )
        return view
