from django.db import models

from .json import ArrayField, JSONField

ORDERING_ACCEPTED_FIELDS = (
    models.BigIntegerField,
    models.IntegerField,
    models.PositiveIntegerField,
    models.PositiveSmallIntegerField,
    models.SmallIntegerField,
)

__all__ = ["JSONField", "ArrayField", "ORDERING_ACCEPTED_FIELDS"]
