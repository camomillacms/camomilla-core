from functools import cached_property
from typing import Iterable, List
from modeltranslation import settings as mt_settings
from modeltranslation.translator import NotRegistered, translator
from modeltranslation.utils import build_localized_fieldname
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from camomilla.utils.getters import pointed_getter
from camomilla.utils.translation import is_translatable
from camomilla.utils.translation import nest_to_plain, plain_to_nest
from camomilla.settings import API_TRANSLATION_ACCESSOR


class TranslationsMixin(serializers.ModelSerializer):
    """
    This mixin adds support for modeltranslation fields.
    It automatically nests all translations fields (es. title_en) under a "translations" field.

    This means that, in representation, the serializer will transform:
    `{"title_en": "Hello", "title_it": "Ciao"}` -> `{"translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}`

    While in deserialization, the serializer will transform:
    `{"translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}` -> `{"title_en": "Hello", "title_it": "Ciao"}`
    """

    def _transform_input(self, data):
        return nest_to_plain(
            data, self.translation_fields or [], API_TRANSLATION_ACCESSOR
        )

    def _transform_output(self, data):
        return plain_to_nest(
            data, self.translation_fields or [], API_TRANSLATION_ACCESSOR
        )

    @cached_property
    def translation_fields(self) -> List[str]:
        try:
            return translator.get_options_for_model(self.Meta.model).get_field_names()
        except NotRegistered:
            return []

    @property
    def _writable_fields(self) -> Iterable[serializers.Field]:
        for field in super()._writable_fields:
            if field.field_name not in self.translation_fields:
                yield field

    def to_internal_value(self, data):
        return super().to_internal_value(self._transform_input(data))

    def to_representation(self, instance):
        return self._transform_output(super().to_representation(instance))

    def run_validation(self, *args, **kwargs):
        try:
            return super().run_validation(*args, **kwargs)
        except ValidationError as ex:
            ex.detail.update(self._transform_input(ex.detail))
            raise ValidationError(detail=ex.detail)

    @property
    def is_translatable(self):
        return is_translatable(pointed_getter(self, "Meta.model"))


class RemoveTranslationsMixin(serializers.ModelSerializer):
    """
    This mixin removes all translations fields (es. title_en) from the serializer.
    It's useful when you want to create a serializer that doesn't need to include all translations fields.

    If request is passed in context, this serializer becomes aware of the query parameter "included_translations".
    If the value is "all", all translations fields are included.
    If the value is a comma separated list of languages (es. "en,it"), only the specified translations fields are included.
    """

    @cached_property
    def translation_fields(self):
        try:
            return translator.get_options_for_model(self.Meta.model).get_field_names()
        except NotRegistered:
            return []

    def get_default_field_names(self, declared_fields, model_info):
        request = self.context.get("request", False)
        included_translations = request and request.GET.get(
            "included_translations", False
        )
        if included_translations == "all":
            return super().get_default_field_names(declared_fields, model_info)
        elif included_translations is not False:
            included_translations = included_translations.split(",")
        else:
            included_translations = []

        field_names = super().get_default_field_names(declared_fields, model_info)
        for lang in mt_settings.AVAILABLE_LANGUAGES:
            if lang not in included_translations:
                for field in self.translation_fields:
                    localized_fieldname = build_localized_fieldname(field, lang)
                    if localized_fieldname in field_names:
                        field_names.remove(localized_fieldname)
        return field_names
