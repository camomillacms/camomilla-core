from typing import Optional, List
from django.db import models
from rest_framework import serializers
from structured.fields import StructuredJSONField
from structured.pydantic.fields import QuerySet
from structured.pydantic.models import BaseModel
from camomilla import model_api
from .serializers import CustomBaseArgumentsRegisterModelSerializer
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
    fk_field = models.ForeignKey(SimpleRelationModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="fk_field")
    m2m_field = models.ManyToManyField(SimpleRelationModel, blank=True, related_name="m2m_field")

    def __str__(self) -> str:
        return self.title


@model_api.register(
    base_serializer=CustomBaseArgumentsRegisterModelSerializer,
    base_viewset=CustomBaseArgumentsRegisterModelViewSet
)
class CustomBaseArgumentsRegisterModel(models.Model):
    description = models.CharField(max_length=255)
    def __str__(self) -> str:
        return self.description


@model_api.register(
    serializer_meta={"fields": ["name"]},
    viewset_attrs={"search_fields": ["name"]}
)
class CustomArgumentsRegisterModel(models.Model):
    name = models.CharField(max_length=255)
    def __str__(self) -> str:
        return self.name


@model_api.register(
    filters={"field_filtered__icontains": "test"}
)
class FilteredRegisterModel(models.Model):
    field_filtered = models.CharField(max_length=255)
    def __str__(self) -> str:
        return self.field_filtered
