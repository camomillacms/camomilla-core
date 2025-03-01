from collections import OrderedDict
from rest_framework import serializers, relations


class RelatedField(serializers.PrimaryKeyRelatedField):
    """
    This field helps to serialize and deserialize related data.
    It serializes related data building a nested serializer.
    Allowing insertions with both nested and plain data.


    For example it accepts as input data both:
    ```json
    {"related_field": 1}
    {"related_field": {"id": 1, "field": "value"}}
    ```

    """

    def __init__(self, **kwargs):
        self.inherited_fields_filter = kwargs.pop("inherited_fields_filter", [])
        self.serializer = kwargs.pop("serializer", None)
        self.lookup = kwargs.pop("lookup", "id")
        if self.serializer is not None:
            assert issubclass(
                self.serializer, serializers.Serializer
            ), '"serializer" is not a valid serializer class'
            assert hasattr(
                self.serializer.Meta, "model"
            ), 'Class {serializer_class} missing "Meta.model" attribute'.format(
                serializer_class=self.serializer.__class__.__name__
            )
            if not kwargs.get("read_only", False):
                kwargs["queryset"] = kwargs.get(
                    "queryset", self.serializer.Meta.model.objects.all()
                )
            self.allow_insert = kwargs.pop("allow_insert", False)
            # kwargs["allow_null"] = kwargs.get("allow_null", self.serializer.Meta.model._meta.get_field(self.source).null)
        super().__init__(**kwargs)

    def use_pk_only_optimization(self):
        return False if self.serializer else True

    def to_representation(self, instance):
        if self.serializer:
            kwargs = {"context": self.context}
            if self.inherited_fields_filter:
                kwargs["inherited_fields_filter"] = self.inherited_fields_filter
            return self.serializer(instance, **kwargs).data
        return super().to_representation(instance)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            instance = (
                self.get_queryset()
                .filter(**{self.lookup: data.get(self.lookup, None)})
                .first()
            )
            if self.allow_insert is True and len(data.keys()) and self.serializer:
                serialized_data = self.serializer(
                    instance=instance, data=data, context=self.context
                )
                if serialized_data.is_valid(raise_exception=ValueError):
                    instance = serialized_data.save()
            return instance
        return super().to_internal_value(data)

    def get_choices(self, cutoff=None):
        queryset = self.get_queryset()
        if queryset is None:
            return {}
        if cutoff is not None:
            queryset = queryset[:cutoff]

        return OrderedDict(
            [
                (
                    super(RelatedField, self).to_representation(item),
                    self.display_value(item),
                )
                for item in queryset
            ]
        )

    @classmethod
    def many_init(cls, *args, **kwargs):
        class ManyRelatedField(serializers.ManyRelatedField):
            def to_internal_value(self, data):
                if isinstance(data, str) or not hasattr(data, "__iter__"):
                    self.fail("not_a_list", input_type=type(data).__name__)
                if not self.allow_empty and len(data) == 0:
                    self.fail("empty")

                child = self.child_relation
                instances = {
                    getattr(item, child.lookup): item
                    for item in child.get_queryset().filter(
                        **{
                            f"{child.lookup}__in": [
                                (
                                    item.get(child.lookup, None)
                                    if isinstance(item, dict)
                                    else item
                                )
                                for item in data
                            ]
                        }
                    )
                }
                if child.allow_insert is True and len(data.keys()) and child.serializer:
                    for item in data:
                        serialized_data = child.serializer(
                            instance=instances.get(item.get(child.lookup)),
                            data=item,
                            context=child.context,
                        )
                        if serialized_data.is_valid(raise_exception=ValueError):
                            instance = serialized_data.save()
                            instances[instance.pk] = instance
                return instances.values()

        list_kwargs = {"child_relation": cls(*args, **kwargs)}
        for key in kwargs:
            if key in relations.MANY_RELATION_KWARGS:
                list_kwargs[key] = kwargs[key]
        return ManyRelatedField(**list_kwargs)
