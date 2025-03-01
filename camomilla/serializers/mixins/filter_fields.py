from rest_framework import serializers
from camomilla.serializers.fields.related import RelatedField
from collections import defaultdict


class FilterFieldsMixin(serializers.ModelSerializer):
    """
    Mixin to filter fields from a serializer, including handling nested fields.
    """

    def __init__(self, *args, **kwargs):
        self.inherited_fields_filter = kwargs.pop("inherited_fields_filter", [])
        return super().__init__(*args, **kwargs)

    inherited_fields_filter = []

    def get_default_field_names(self, *args):
        field_names = super().get_default_field_names(*args)
        request = self.context.get("request", None)

        if request is not None and request.method == "GET":
            fields = request.query_params.get("fields", "").split(",")
            fields = [f for f in fields if f != ""]
            if len(self.inherited_fields_filter) > 0:
                fields = self.inherited_fields_filter

            self.filtered_fields = set()
            self.childs_fields = defaultdict(set)
            for field in fields:
                if "__" in field:
                    parent_field, child_field = field.split("__", 1)
                    if parent_field in field_names:
                        self.filtered_fields.add(parent_field)
                        self.childs_fields[parent_field].add(child_field)
                else:
                    if field in field_names:
                        self.filtered_fields.add(field)

            if len(self.filtered_fields) > 0:
                return list(self.filtered_fields)
            else:
                return field_names

        return field_names

    def build_field(self, field_name, info, model_class, nested_depth):
        field_class, field_kwargs = super().build_field(
            field_name, info, model_class, nested_depth
        )
        inherited_fields_filter = (
            self.childs_fields.get(field_name, [])
            if hasattr(self, "childs_fields")
            else []
        )
        if len(inherited_fields_filter) > 0 and issubclass(field_class, RelatedField):
            field_kwargs["inherited_fields_filter"] = list(inherited_fields_filter)
        return field_class, field_kwargs
