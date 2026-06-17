from typing import Optional, Tuple, Type


def get_standard_bases() -> tuple:
    """Default base classes for a *read-shaped* model serializer.

    Includes ``RemoveTranslationsMixin`` so the output is flat
    (``title_en`` rather than nested ``translations.en.title``) and
    ``SetupEagerLoadingMixin`` for query-perf on nested reads.

    Use ``get_editable_bases`` instead when you need to deserialize
    nested PATCH payloads (publish flow, draft application).
    """
    from rest_framework.serializers import ModelSerializer
    from camomilla.serializers.mixins import (
        JSONFieldPatchMixin,
        NestMixin,
        OrderingMixin,
        SetupEagerLoadingMixin,
        FieldsOverrideMixin,
        FilterFieldsMixin,
        RemoveTranslationsMixin,
        SafeNestingMixin,
    )

    return (
        SafeNestingMixin,
        SetupEagerLoadingMixin,
        FilterFieldsMixin,
        NestMixin,
        FieldsOverrideMixin,
        JSONFieldPatchMixin,
        OrderingMixin,
        RemoveTranslationsMixin,
        ModelSerializer,
    )


def get_editable_bases(page_mixin: Optional[Type] = None) -> tuple:
    """Default base classes for a *write-shaped* model serializer.

    The chain keeps ``TranslationsMixin`` (via ``BaseModelSerializer``) so
    nested PATCH payloads — e.g. ``{"translations": {"en": {"title": …}}}``
    — round-trip the way the API expects. Used by the publish pipeline
    when applying ``draft_data`` through the serializer chain.

    ``page_mixin`` lets a caller plug a project-specific serializer mixin
    (typically the one resolved via ``AbstractPage.get_serializer()``);
    falls back to ``AbstractPageMixin``.
    """
    from camomilla.serializers.base import BaseModelSerializer
    from camomilla.serializers.mixins import AbstractPageMixin

    base = page_mixin or AbstractPageMixin
    if not isinstance(base, type) or not issubclass(base, AbstractPageMixin):
        base = AbstractPageMixin
    return (base, BaseModelSerializer)


def build_standard_model_serializer(
    model,
    depth: Optional[int] = None,
    bases: Optional[Tuple[Type, ...]] = None,
    name_suffix: str = "Standard",
):
    """Dynamically build a ``ModelSerializer`` subclass for ``model``.

    Parameters
    ----------
    model
        The Django model the serializer wraps.
    depth
        ``Meta.depth`` value — pass an int for nested-read serializers,
        omit entirely for write-shaped ones (DRF defaults to ``0``).
    bases
        Base classes for the new serializer. Defaults to
        :func:`get_standard_bases` (read-shaped). For write-shaped
        serializers, pass :func:`get_editable_bases`.
    name_suffix
        Suffix used to compose the dynamically-generated class name.
        ``"Standard"`` for read serializers, ``"Draft"`` (or similar)
        for write ones — appears in tracebacks and debugger output.
    """
    if bases is None:
        bases = get_standard_bases()
    meta_attrs = {"model": model, "fields": "__all__"}
    if depth is not None:
        meta_attrs["depth"] = depth
    return type(
        f"{model.__name__}{name_suffix}Serializer",
        bases,
        {"Meta": type("Meta", (object,), meta_attrs)},
    )
