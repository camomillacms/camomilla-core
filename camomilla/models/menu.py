from uuid import uuid4
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils.safestring import mark_safe
from pydantic import Field
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField
from camomilla.types import Permalink, LinkTypes
from typing import Union, List


# ``MenuNodeLink`` used to live here as the canonical polymorphic link
# primitive. It now lives in :mod:`camomilla.types` as :class:`Permalink`
# so other ``template_data`` schemas (not just menus) can use the same
# shape. The alias keeps any legacy importer working.
MenuNodeLink = Permalink
__all__ = ["LinkTypes", "MenuNodeLink", "MenuNode", "Menu"]


class MenuNode(BaseModel):
    id: str = Field(default_factory=uuid4)
    meta: dict = {}
    nodes: List["MenuNode"] = []
    title: str = ""
    link: Permalink


class Menu(models.Model):
    key = models.CharField(max_length=200, unique=True, editable=True, default=uuid4)
    available_classes = models.JSONField(default=dict, editable=False)
    enabled = models.BooleanField(default=True)
    nodes = StructuredJSONField(default=list, schema=MenuNode)

    class Meta:
        verbose_name = _("menu")
        verbose_name_plural = _("menus")

    def render(
        self,
        template_path: str,
        request=None,
        context: Union[dict, RequestContext] = {},
    ):
        if isinstance(context, RequestContext):
            context = context.flatten()
        # Always bind ``request`` (even as ``None``) so a menu template can
        # safely do ``{{ item|node_url:request }}`` to get absolute URLs.
        # Without this, a render without a request would raise
        # ``VariableDoesNotExist`` on the unresolved ``request`` filter arg.
        context = {"request": request, **context, "menu": self}
        return mark_safe(render_to_string(template_path, context, request))

    class defaultdict(dict):
        def __missing__(self, key):
            dict.__setitem__(self, key, Menu.objects.get_or_create(key=key)[0])
            return self[key]

    def __str__(self) -> str:
        return self.key
