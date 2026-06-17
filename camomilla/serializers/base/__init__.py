from rest_framework import serializers

from camomilla.serializers.mixins import (
    JSONFieldPatchMixin,
    NestMixin,
    OrderingMixin,
    SafeNestingMixin,
    SetupEagerLoadingMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin,
    TranslationsMixin,
)
from camomilla.settings import ENABLE_TRANSLATIONS

bases = (
    # First in the MRO so its build_(nested|relational)_field overrides win:
    # any FK/O2O/M2M to the auth user model nests through the blacklist
    # serializer instead of dumping the password hash / privilege columns.
    SafeNestingMixin,
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
