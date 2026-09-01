from rest_framework import serializers
from rest_framework.schemas.openapi import (
    SchemaGenerator as DRFSchemaGenerator,
    AutoSchema as DRFAutoSchema,
)
from camomilla.utils.getters import find_and_replace_dict
from camomilla.utils.translation import plain_to_nest
from camomilla.settings import API_TRANSLATION_ACCESSOR
from modeltranslation.utils import build_localized_fieldname

from camomilla.serializers.mixins import TranslationsMixin
from camomilla.settings import LANGUAGE_CODES
from camomilla.utils.routes import endpoint_for_model
from structured.contrib.restframework import StructuredJSONField


class AutoSchema(DRFAutoSchema):
    extra_components = {}

    def map_serializer(self, serializer):
        schema = super(AutoSchema, self).map_serializer(serializer)
        if isinstance(serializer, TranslationsMixin) and serializer.is_translatable:
            # Pass the accessor explicitly: plain_to_nest defaults to "translations"
            # while the lookup below uses API_TRANSLATION_ACCESSOR, so a project
            # that customises the setting used to raise KeyError right here.
            schema = plain_to_nest(
                schema["properties"],
                serializer.translation_fields,
                API_TRANSLATION_ACCESSOR,
            )
            schema.setdefault(API_TRANSLATION_ACCESSOR, {})
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
        view.schema._view = view
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


class FormAutoSchema(AutoSchema):
    """
    Flat, form-oriented JSON Schema — the variant served on ``OPTIONS``.

    It deliberately does NOT nest translations. The nested ``translations``
    envelope is a transport detail, not a field: an admin edits "title, which has
    a value per language", and a form generator handed the envelope has no good
    way to render it. Emitting it produced either a text input bound to the whole
    ``{it: ..., en: ...}`` object (one keystroke wipes every language) or an
    unknown object type, plus a duplicate top-level input per translated field
    whose value ``nest_to_plain`` silently discards on save.

    So each field appears exactly once, carrying ``translatable: true`` when it
    has per-language values. Where to WRITE those values is published separately
    as ``lang_info.accessor``.

    This does not contradict ``/openapi``: that endpoint documents the wire
    contract and keeps the envelope. OPTIONS exists so a client can build a form,
    which is a different question.
    """

    def map_field(self, field):
        """
        Describe relations as relations.

        DRF maps a PrimaryKeyRelatedField to ``{"type": "integer"}``, which tells
        a form generator to render a number input and expect the editor to know
        a database id. Worse, SimpleMetadata collapses FKs, M2Ms, JSONFields and
        SerializerMethodFields to the same opaque payload, so a client cannot
        even tell them apart.

        The key names mirror ``structured.utils.options.build_relation_schema_options``
        on purpose, so a structured-field relation and a plain DRF relation look
        identical to a client. ``endpoint`` is added here because that is what a
        client needs in order to fetch options; structured's select2/ajax block
        is deliberately not copied, since it points at structured's own search
        view rather than this API.

        ``model`` is published instead of a widget name: deciding that
        ``camomilla.Media`` deserves a media picker rather than a generic
        autocomplete is the client's call, not the API's.
        """
        many = isinstance(field, serializers.ManyRelatedField)
        relation = field.child_relation if many else field

        if isinstance(relation, serializers.RelatedField):
            model = getattr(getattr(relation, "queryset", None), "model", None)
            if model is not None:
                schema = {
                    "type": "relation",
                    "model": f"{model._meta.app_label}.{model.__name__}",
                    "multiple": many,
                }
                endpoint = endpoint_for_model(model)
                if endpoint:
                    schema["endpoint"] = endpoint
                return schema

        return super().map_field(field)

    def map_serializer(self, serializer):
        # Skip AutoSchema.map_serializer (which nests) but keep its map_field
        # override, so StructuredJSONField still contributes its own JSON Schema.
        schema = DRFAutoSchema.map_serializer(self, serializer)

        translated = set(getattr(serializer, "translation_fields", None) or [])
        properties = schema.get("properties", {})

        # Drop the localized twins (title_it, title_en, ...). serializer.fields
        # still carries them — TranslationsMixin hides them from writes and folds
        # them into the envelope — so without the nesting step they resurface,
        # and a generator would render title AND title_it AND title_en.
        localized = {
            build_localized_fieldname(base, code)
            for base in translated
            for code in LANGUAGE_CODES
        }
        for name in localized & set(properties):
            del properties[name]
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r not in localized]

        for field in serializer.fields.values():
            name = self.get_field_name(field)
            prop = properties.get(name)
            if prop is None:
                continue
            if name in translated:
                prop["translatable"] = True
            # DRF's OpenAPI omits labels; a form generator needs them, and
            # useFormFromSchema reads `title`.
            if getattr(field, "label", None):
                prop.setdefault("title", str(field.label))
            # A Django TextField becomes an unbounded CharField, so the usual
            # "maxLength > 255 means multiline" heuristic never fires and an
            # article body would render as a single-line input. DRF already
            # knows — it sets this style for TextField — so say so explicitly.
            if (
                prop.get("type") == "string"
                and "format" not in prop
                and getattr(field, "style", {}).get("base_template")
                == "textarea.html"
            ):
                prop["format"] = "textarea"

        return schema
