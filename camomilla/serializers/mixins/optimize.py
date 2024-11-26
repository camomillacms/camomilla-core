from rest_framework.utils import model_meta


class Optimizations:
    only = set()
    select_related = set()
    prefetch_related = set()

    def __init__(self):
        self.only = set()
        self.select_related = set()
        self.prefetch_related = set()

    def __str__(self):
        return f"Optimizations(only={self.only}, select_related={self.select_related}, prefetch_related={self.prefetch_related})"


def recursive_extract_optimizations(fields, info, max_depth=100) -> Optimizations:
    optimizations = Optimizations()
    if max_depth == 0:
        return optimizations
    for field in fields:
        if "__" in field and field not in info.fields:
            field_part_1, field_part_2 = field.split("__", 1)
            if field_part_1 in info.relations:
                field_info = info.relations[field_part_1]
                nested_info = model_meta.get_field_info(field_info.related_model)
                if field_info.to_many:
                    optimizations.prefetch_related.add(field_part_1)
                    optimizations.only.add(field_part_1)
                else:
                    optimizations.select_related.add(field_part_1)
                    optimizations.only.add(field_part_1)
                nested_optimizations = recursive_extract_optimizations(
                    [field_part_2], nested_info, max_depth - 1
                )

                for nested_field in nested_optimizations.only:
                    optimizations.only.add(f"{field_part_1}__{nested_field}")
                for nested_field in nested_optimizations.select_related:
                    optimizations.select_related.add(f"{field_part_1}__{nested_field}")
                for nested_field in nested_optimizations.prefetch_related:
                    optimizations.prefetch_related.add(
                        f"{field_part_1}__{nested_field}"
                    )
        else:
            if field in info.relations:
                if info.relations[field].to_many:
                    optimizations.prefetch_related.add(field)
                else:
                    optimizations.select_related.add(field)
                optimizations.only.add(field)
            elif field in info.fields:
                optimizations.only.add(field)
    return optimizations


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
            serializer_fields = cls(context=context).fields.keys()
            filtered_fields = set()
            for field in request.query_params.get("fields", "").split(","):
                filtered_fields.add(field)
            if len(filtered_fields) == 0:
                filtered_fields = serializer_fields
            model = getattr(cls.Meta, "model", None)
            if not model:
                return queryset
            optimizations = recursive_extract_optimizations(
                filtered_fields, model_meta.get_field_info(model)
            )
            if len(optimizations.only) > 0:
                queryset = queryset.only(*optimizations.only)
            if len(optimizations.select_related) > 0:
                queryset = queryset.select_related(*optimizations.select_related)
            if len(optimizations.prefetch_related) > 0:
                queryset = queryset.prefetch_related(*optimizations.prefetch_related)
        return queryset
