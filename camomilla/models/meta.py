from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from structured.fields import StructuredJSONField

from camomilla.meta.schema_builder import MetaTypeFieldDef
from camomilla.meta import compiler as meta_compiler


class MetaType(models.Model):
    """
    A user-defined "type" describing the shape of a MetaInstance.

    The ``schema`` field is a list of MetaTypeFieldDef rows declared by an
    editor in the admin (string, media, group, list, ...). When the MetaType
    is saved, the runtime Pydantic compiler cache is invalidated so any
    MetaInstance form/serializer using it picks up the new shape.
    """

    key = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    schema = StructuredJSONField(default=list, schema=MetaTypeFieldDef)
    compiled_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("meta type")
        verbose_name_plural = _("meta types")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name or self.key

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        meta_compiler.clear_cache(self.pk)

    def get_pydantic_model(self):
        return meta_compiler.build_pydantic_model(self)

    def get_json_schema(self) -> dict:
        return meta_compiler.get_json_schema(self)


class MetaInstance(models.Model):
    """
    Concrete entry whose shape is dictated by its referenced MetaType.

    ``data`` is stored as a plain JSONField because StructuredJSONField needs
    its schema at class load time. We validate ``data`` against the runtime
    Pydantic model built from ``meta_type`` in ``clean()`` (and at the
    serializer level for the API).
    """

    meta_type = models.ForeignKey(
        MetaType, on_delete=models.PROTECT, related_name="instances"
    )
    identifier = models.SlugField(max_length=200, blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("meta instance")
        verbose_name_plural = _("meta instances")
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return self.identifier or f"{self.meta_type} #{self.pk}"

    def clean(self):
        super().clean()
        if self.meta_type_id is None:
            return
        model_cls = self.meta_type.get_pydantic_model()
        try:
            validated = model_cls.model_validate(self.data or {})
        except Exception as exc:  # pydantic ValidationError
            raise ValidationError({"data": str(exc)})
        self.data = validated.model_dump(mode="json")
