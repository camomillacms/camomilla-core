def get_standard_bases() -> tuple:
    from rest_framework.serializers import ModelSerializer
    from camomilla.serializers.mixins import (
        JSONFieldPatchMixin,
        NestMixin,
        OrderingMixin,
        SetupEagerLoadingMixin,
        FieldsOverrideMixin,
        FilterFieldsMixin,
        RemoveTranslationsMixin,
    )

    return (
        SetupEagerLoadingMixin,
        FilterFieldsMixin,
        NestMixin,
        FieldsOverrideMixin,
        JSONFieldPatchMixin,
        OrderingMixin,
        RemoveTranslationsMixin,
        ModelSerializer,
    )


def build_standard_model_serializer(model, depth, bases=None):
    if bases is None:
        bases = get_standard_bases()
    return type(
        f"{model.__name__}StandardSerializer",
        bases,
        {
            "Meta": type(
                "Meta",
                (object,),
                {"model": model, "depth": depth, "fields": "__all__"},
            )
        },
    )
