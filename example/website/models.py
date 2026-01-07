from typing import Optional, List
from django.db import models
from camomilla.models import AbstractPage, Media
from structured.fields import StructuredJSONField
from structured.pydantic.fields import QuerySet
from structured.pydantic.models import BaseModel
from camomilla import model_api
from .views import CustomBaseArgumentsRegisterModelViewSet


@model_api.register()
class SimpleRelationModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


class TestSchema(BaseModel):
    name: str
    age: int = None
    child: Optional["TestSchema"] = None
    childs: List["TestSchema"] = []
    fk_field: SimpleRelationModel = None
    qs_field: QuerySet[SimpleRelationModel]


def init_schema():
    return TestSchema(name="")


@model_api.register()
class TestModel(models.Model):
    title = models.CharField(max_length=255)
    structured_data = StructuredJSONField(schema=TestSchema, default=init_schema)
    fk_field = models.ForeignKey(
        SimpleRelationModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fk_field",
    )
    m2m_field = models.ManyToManyField(
        SimpleRelationModel, blank=True, related_name="m2m_field"
    )

    def __str__(self) -> str:
        return self.title


@model_api.register(
    base_serializer=CustomBaseArgumentsRegisterModelViewSet.CustomBaseArgumentsRegisterModelSerializer,
    base_viewset=CustomBaseArgumentsRegisterModelViewSet,
)
class CustomBaseArgumentsRegisterModel(models.Model):
    description = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.description


@model_api.register(
    serializer_meta={"fields": ["name"]}, viewset_attrs={"search_fields": ["name"]}
)
class CustomArgumentsRegisterModel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.name


@model_api.register(filters={"field_filtered__icontains": "test"})
class FilteredRegisterModel(models.Model):
    field_filtered = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.field_filtered


def inject_context_func(request, super_ctx):
    return {
        "injected_from_meta": {
            "title": "👻 I'm beeing injected!",
            "media_gallery": Media.objects.all(),
        }
    }


@model_api.register()
class CustomPageMetaModel(AbstractPage):
    custom_field = models.CharField(max_length=255, blank=True, null=True)
    custom_parent_page = models.ForeignKey(
        "camomilla.Page",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="custom_children_pages",
    )

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Custom Page"
        verbose_name_plural = "Custom Pages"

    class PageMeta:
        parent_page_field = "custom_parent_page"
        default_template = "website/page_custom_meta_template.html"
        inject_context_func = inject_context_func
        standard_serializer = "example.website.serializers.CustomPageSerializer"


@model_api.register()
class ExposedRelatedPageModel(AbstractPage):
    class Meta:
        verbose_name = "Exposed related Page"
        verbose_name_plural = "Exposed related Pages"

    class PageMeta:
        standard_serializer = (
            "example.website.serializers.ExposedRelatedPageModelSerializer"
        )


@model_api.register()
class UnexposedRelatedPageModel(AbstractPage):
    class Meta:
        verbose_name = "Unexposed related Page"
        verbose_name_plural = "Unexposed related Pages"


@model_api.register()
class RelatedPageModel(AbstractPage):
    exposed_pages = models.ManyToManyField(
        ExposedRelatedPageModel,
        blank=True,
        related_name="related_pages",
    )
    unexposed_pages = models.ManyToManyField(
        UnexposedRelatedPageModel,
        blank=True,
        related_name="related_pages",
    )

    class Meta:
        verbose_name = "Related Page"
        verbose_name_plural = "Related Pages"

    class PageMeta:
        standard_serializer = "example.website.serializers.RelatedPageModelSerializer"


class InvalidPageMetaModel(CustomPageMetaModel):
    class PageMeta:
        standard_serializer = "example.website.serializers.InvalidSerializer"


@model_api.register()
class DefaultApiSerializerModel(AbstractPage):
    description = models.TextField(null=True, blank=True)


@model_api.register()
class CustomApiSerializerModel(AbstractPage):
    description = models.TextField(null=True, blank=True)

    class PageMeta:
        standard_serializer = "example.website.serializers.CustomApiSerializerModelSerializer"

