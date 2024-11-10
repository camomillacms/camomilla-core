from rest_framework import serializers

from ...contrib.rest_framework.serializer import TranslationsMixin
from camomilla.serializers.mixins import (
    JSONFieldPatchMixin,
    NestMixin,
    OrderingMixin,
    SetupEagerLoadingMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin
)


class BaseModelSerializer(
    SetupEagerLoadingMixin,
    NestMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin,
    JSONFieldPatchMixin,
    OrderingMixin,
    TranslationsMixin,
    serializers.ModelSerializer,
):
    """
    This is the base serializer for all the models.
    It adds support for:
    - nesting translations fields under a "translations" field
    - overriding related fields with auto-generated serializers
    - patching JSONField
    - ordering
    - eager loading
    """

    pass


__all__ = [
    "BaseModelSerializer",
]
