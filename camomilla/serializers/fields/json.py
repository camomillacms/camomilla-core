from pydantic import TypeAdapter, ValidationError
from rest_framework import serializers
from rest_framework.utils import model_meta
from typing import TYPE_CHECKING, Any, Union, Dict, List

from camomilla.utils.setters import pointed_setter

if TYPE_CHECKING:
    from structured.pydantic.models import BaseModel


class StructuredJSONField(serializers.JSONField):
    """
    This field allows to serialize and deserialize structured data.
    """

    schema: Union["BaseModel", TypeAdapter] = None

    def __init__(self, **kwargs):
        self.schema = kwargs.pop("schema", None)
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        if self.schema is None and isinstance(parent, serializers.ModelSerializer):
            info = model_meta.get_field_info(parent.Meta.model)
            field = info.fields[field_name]
            self.schema = field.schema
            self.many = field.many
            self.json_schema = field.schema.json_schema()
        super().bind(field_name, parent)

    def to_representation(self, instance: Union["BaseModel", List["BaseModel"]]):
        if isinstance(instance, list) and self.many:
            return super().to_representation(
                self.schema.dump_python(instance, exclude_unset=True)
            )
        return super().to_representation(instance.model_dump(exclude_unset=True))

    def to_internal_value(self, data: Union[list, dict]):
        try:
            return self.schema.validate_python(super().to_internal_value(data))
        except ValidationError as e:
            drf_error: Union[list, Dict[str, Any]] = [] if self.many else {}
            for error in e.errors():
                pointed_setter(
                    drf_error, ".".join([str(x) for x in error["loc"]]), [error["msg"]]
                )
            raise serializers.ValidationError(drf_error)
