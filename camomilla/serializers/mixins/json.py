import django
from rest_framework.utils import model_meta

from camomilla.utils import dict_merge

if django.VERSION >= (4, 0):
    from django.db.models import JSONField as DjangoJSONField
else:
    from django.contrib.postgres.fields import JSONField as DjangoJSONField


class JSONFieldPatchMixin:
    """
    This mixin allows to patch JSONField values during partial updates.
    This means that, if a JSONField is present in the request and the requsest uses PATCH method,
    the serializer will merge the new data with the old one.
    """

    def is_json_field(self, attr, value, info):
        return (
            attr in info.fields
            and isinstance(info.fields[attr], DjangoJSONField)
            and isinstance(value, dict)
        )

    def update(self, instance, validated_data):
        if self.partial:
            info = model_meta.get_field_info(instance)
            for attr, value in validated_data.items():
                if self.is_json_field(attr, value, info):
                    validated_data[attr] = dict_merge(
                        getattr(instance, attr, {}), value
                    )
        return super().update(instance, validated_data)
