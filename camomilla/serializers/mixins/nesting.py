from camomilla.serializers.fields.related import RelatedField
from camomilla.serializers.utils import build_standard_model_serializer
from camomilla import settings


class NestMixin:
    """
    This mixin automatically creates nested serializers for relational fields.
    The depth of the nesting can be set using the "depth" attribute of the Meta class.
    If the depth is not set, the serializer will use the value coming from the settings.

    CAMOMILLA = { "API": {"NESTING_DEPTH": 10} }
    """

    def __init__(self, *args, **kwargs):
        self._depth = kwargs.pop("depth", None)
        return super().__init__(*args, **kwargs)

    def build_nested_field(self, field_name, relation_info, nested_depth):
        return self.build_relational_field(field_name, relation_info, nested_depth)

    def build_relational_field(
        self, field_name, relation_info, nested_depth=settings.API_NESTING_DEPTH + 1
    ):
        nested_depth = nested_depth if self._depth is None else self._depth
        field_class, field_kwargs = super().build_relational_field(
            field_name, relation_info
        )
        if (
            field_class is RelatedField and nested_depth > 1
        ):  # stop recursion one step before the jump :P
            field_kwargs["serializer"] = build_standard_model_serializer(
                relation_info[1], nested_depth - 1
            )
        return field_class, field_kwargs
