from rest_framework import serializers

from camomilla.serializers.mixins import (
    JSONFieldPatchMixin,
    NestMixin,
    OrderingMixin,
    SetupEagerLoadingMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin,
    TranslationsMixin,
)
from camomilla.settings import ENABLE_TRANSLATIONS

bases = (
    SetupEagerLoadingMixin,
    NestMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin,
    JSONFieldPatchMixin,
    OrderingMixin,
)

if ENABLE_TRANSLATIONS:
    bases += (TranslationsMixin,)


class BaseModelSerializer(*bases, serializers.ModelSerializer):
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
