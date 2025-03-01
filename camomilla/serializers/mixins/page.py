from rest_framework import serializers
from camomilla.models import UrlNode
from camomilla.serializers.validators import UniquePermalinkValidator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from camomilla.models.page import AbstractPage


class AbstractPageMixin(serializers.ModelSerializer):
    """
    This mixin is needed to serialize AbstractPage models.
    It provides permalink validation and some extra fields serialization.

    Use it as a base class for your serializer if you need to serialize custom AbstractPage models.
    """

    breadcrumbs = serializers.SerializerMethodField()
    routerlink = serializers.CharField(read_only=True)
    template_file = serializers.SerializerMethodField()

    def get_template_file(self, instance: "AbstractPage"):
        return instance.get_template_path()

    def get_breadcrumbs(self, instance: "AbstractPage"):
        return instance.breadcrumbs

    @property
    def translation_fields(self):
        return super().translation_fields + ["permalink"]

    def get_default_field_names(self, *args):
        from camomilla.serializers.mixins.translation import RemoveTranslationsMixin

        default_fields = super().get_default_field_names(*args)
        filtered_fields = getattr(self, "filtered_fields", [])
        if len(filtered_fields) > 0:
            return filtered_fields
        if RemoveTranslationsMixin in self.__class__.__bases__:  # noqa: E501
            return default_fields
        return list(
            set(
                [f for f in default_fields if f != "url_node"]
                + UrlNode.LANG_PERMALINK_FIELDS
                + ["permalink"]
            )
        )

    def build_field(self, field_name, info, model_class, nested_depth):
        if field_name in UrlNode.LANG_PERMALINK_FIELDS + ["permalink"]:
            return serializers.CharField, {
                "required": False,
                "allow_blank": True,
            }
        return super().build_field(field_name, info, model_class, nested_depth)

    def get_validators(self):
        return super().get_validators() + [UniquePermalinkValidator()]
