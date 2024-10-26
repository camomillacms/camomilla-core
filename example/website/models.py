from __future__ import annotations
from typing import Optional, List
from django.db import models
from structured.fields import StructuredJSONField
from structured.pydantic.fields import ForeignKey, QuerySet
from structured.pydantic.models import BaseModel
from camomilla.model_api import register


@register()
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
    qs_field: QuerySet["SimpleRelationModel"]


def init_schema():
    return TestSchema(name="")


@register()
class TestModel(models.Model):
    title = models.CharField(max_length=255)
    structured_data = StructuredJSONField(schema=TestSchema, default=init_schema)

    def __str__(self) -> str:
        return self.title
