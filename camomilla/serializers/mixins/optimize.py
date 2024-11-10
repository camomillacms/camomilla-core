from rest_framework.utils import model_meta


class SetupEagerLoadingMixin:
    """
    This mixin allows to use the setup_eager_loading method to optimize the queries.
    """

    @classmethod
    def optimize_qs(cls, queryset, context=None):
        if hasattr(cls, "setup_eager_loading"):
            queryset = cls.setup_eager_loading(queryset, context=context)
        return cls.auto_optimize_queryset(queryset, context=context)

    @classmethod
    def auto_optimize_queryset(cls, queryset, context=None):
        request = context.get("request", None)
        if request and request.method == "GET":
            model = getattr(cls.Meta, "model", None)
            info = model_meta.get_field_info(model)
            only = set()
            prefetch_related = set()
            select_related = set()
            serializer_fields = cls(context=context).fields.keys()
            filtered_fields = set()
            for field in request.query_params.get("fields", "").split(","):
                if "__" in field:
                    field, _ = field.split("__", 1)
                if field in serializer_fields:
                    filtered_fields.add(field)
            if len(filtered_fields) == 0:
                filtered_fields = serializer_fields
            for field in filtered_fields:
                complete_field = field
                if "__" in field:
                    field, sub_field = field.split("__", 1)
                    complete_field = f"{field}__{sub_field}"
                if (
                    field in info.forward_relations
                    and not info.forward_relations[field].to_many
                ):
                    select_related.add(field)
                    only.add(complete_field)
                elif (
                    field in info.reverse_relations
                    or field in info.forward_relations
                    and info.forward_relations[field].to_many
                ):
                    prefetch_related.add(field)
                    only.add(complete_field)
                elif field in info.fields or field == info.pk.name:
                    only.add(complete_field)
            if len(only) > 0:
                queryset = queryset.only(*only)
            if len(select_related) > 0:
                queryset = queryset.select_related(*select_related)
            if len(prefetch_related) > 0:
                queryset = queryset.prefetch_related(*prefetch_related)
        return queryset
