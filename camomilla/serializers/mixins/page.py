from functools import cached_property
from rest_framework import serializers
from camomilla.models import UrlNode
from camomilla.serializers.validators import UniquePermalinkValidator
from camomilla.settings import LANGUAGE_CODES
from typing import TYPE_CHECKING
from structured.contrib.restframework import StructuredModelSerializer


if TYPE_CHECKING:
    from camomilla.models.page import AbstractPage


class AbstractPageMixin(StructuredModelSerializer, serializers.ModelSerializer):
    """
    This mixin is needed to serialize AbstractPage models.
    It provides permalink validation and some extra fields serialization.

    Use it as a base class for your serializer if you need to serialize custom AbstractPage models.
    """

    breadcrumbs = serializers.SerializerMethodField()
    routerlink = serializers.CharField(read_only=True)
    template_file = serializers.SerializerMethodField()
    # Computed lifecycle properties surfaced as read-only API fields so
    # clients still see a ``status`` / ``is_public`` flag even though they
    # are no longer stored columns.
    status = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(read_only=True)

    def get_template_file(self, instance: "AbstractPage"):
        return instance.get_template_path()

    def get_breadcrumbs(self, instance: "AbstractPage"):
        return instance.breadcrumbs

    @property
    def translation_fields(self):
        return super().translation_fields + ["permalink"]

    PRIVATE_PAGE_FIELDS = ("draft_data", "has_draft")

    @cached_property
    def _private_page_field_set(self) -> frozenset:
        """Exact-match set of private fields, including modeltranslation
        siblings (``draft_data_en``, ``has_draft_it``, …).

        Built explicitly from :data:`LANGUAGE_CODES` rather than a
        ``startswith`` prefix check so a future field that happens to share
        the prefix (e.g. ``draft_data_archived``) is NOT silently hidden.
        """
        members = set(self.PRIVATE_PAGE_FIELDS)
        for base in self.PRIVATE_PAGE_FIELDS:
            for lang in LANGUAGE_CODES:
                members.add(f"{base}_{lang}")
        return frozenset(members)

    def _is_private_page_field(self, name: str) -> bool:
        return name in self._private_page_field_set

    def get_default_field_names(self, *args):
        from camomilla.serializers.mixins.translation import RemoveTranslationsMixin

        default_fields = super().get_default_field_names(*args)
        default_fields = [
            f for f in default_fields if not self._is_private_page_field(f)
        ]
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
