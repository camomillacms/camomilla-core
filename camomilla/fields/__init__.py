from django.db import models

from .json import JSONField

ORDERING_ACCEPTED_FIELDS = (
    models.BigIntegerField,
    models.IntegerField,
    models.PositiveIntegerField,
    models.PositiveSmallIntegerField,
    models.SmallIntegerField,
)

__all__ = ["JSONField", "ORDERING_ACCEPTED_FIELDS"]