from django.db import models
from rest_framework import serializers

from structured.fields import StructuredJSONField as ModelStructuredJSONField
from camomilla.serializers.fields import FileField, ImageField, RelatedField
from structured.contrib.restframework import StructuredJSONField


class FieldsOverrideMixin:
    """
    This mixin automatically overrides the fields of the serializer with camomilla's backed ones.
    """

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.FileField: FileField,
        models.ImageField: ImageField,
        ModelStructuredJSONField: StructuredJSONField,
    }
    serializer_related_field = RelatedField
