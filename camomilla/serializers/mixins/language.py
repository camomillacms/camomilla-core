from django.conf import settings as django_settings
from django.utils import translation
from rest_framework import serializers


# TODO: decide what to do with LangInfoMixin mixin!
class LangInfoMixin(metaclass=serializers.SerializerMetaclass):
    """
    This mixin adds a "lang_info" field to the serializer.
    This field contains information about the languages available in the site.
    """

    lang_info = serializers.SerializerMethodField("get_lang_info", read_only=True)

    def get_lang_info(self, obj, *args, **kwargs):
        languages = []
        for key, language in django_settings.LANGUAGES:
            languages.append({"id": key, "name": language})
        return {
            "default": django_settings.LANGUAGE_CODE,
            "active": translation.get_language(),
            "site_languages": languages,
        }

    def get_default_field_names(self, *args):
        field_names = super().get_default_field_names(*args)
        self.action = getattr(
            self, "action", self.context and self.context.get("action", "list")
        )
        if self.action != "retrieve":
            return [f for f in field_names if f != "lang_info"]
        return field_names
