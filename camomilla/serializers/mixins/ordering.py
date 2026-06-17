from django.db.models.aggregates import Max
from django.db.models.functions import Coalesce
from rest_framework.fields import CreateOnlyDefault
from camomilla.fields import ORDERING_ACCEPTED_FIELDS


class _MaxOrderDefault:
    """Lazy, create-only ordering default = ``max(order) + 1``.

    Wrapped in ``CreateOnlyDefault`` so DRF evaluates it ONLY during create
    validation — never at field-build time, never on reads. The previous
    eager ``get_max_order() + 1`` ran a ``MAX()`` aggregate every time a read
    serializer built its fields (list / detail / router / preview / SSR), and
    the value is only ever consumed on create — so it was 100% wasted on reads.
    """

    def __init__(self, model, order_field):
        self.model = model
        self.order_field = order_field

    def __call__(self):
        return (
            self.model.objects.aggregate(
                max_order=Coalesce(Max(self.order_field), 0)
            )["max_order"]
            + 1
        )

    def __repr__(self):  # keep migrations/debug output stable & side-effect-free
        return "max_order_default()"


class OrderingMixin:
    """
    This mixin allows to set the default value of an ordering field to the max
    value + 1 — lazily and only on create (no aggregate on reads).
    """

    def get_max_order(self, order_field):
        return self.Meta.model.objects.aggregate(
            max_order=Coalesce(Max(order_field), 0)
        )["max_order"]

    def _get_ordering_field_name(self):
        try:
            field_name = self.Meta.model._meta.ordering[0]
            if field_name[0] == "-":
                field_name = field_name[1:]
            return field_name
        except (AttributeError, IndexError):
            return None

    def build_standard_field(self, field_name, model_field):
        field_class, field_kwargs = super().build_standard_field(
            field_name, model_field
        )
        if (
            isinstance(model_field, ORDERING_ACCEPTED_FIELDS)
            and field_name == self._get_ordering_field_name()
        ):
            field_kwargs["default"] = CreateOnlyDefault(
                _MaxOrderDefault(self.Meta.model, field_name)
            )
        return field_class, field_kwargs
