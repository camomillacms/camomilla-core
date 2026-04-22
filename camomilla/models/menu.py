from enum import Enum
from uuid import uuid4
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils.safestring import mark_safe
from pydantic import (
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)
from structured.pydantic.models import BaseModel
from structured.pydantic.conditionals import When, conditional_schema
from structured.fields import StructuredJSONField
from camomilla.models.page import UrlNode, AbstractPage
from typing import Optional, Union, List
from typing_extensions import Annotated
from structured.pydantic.fields.serializer import FieldSerializer
from rest_framework import serializers


class AbstractPageMinimalSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "id": instance.id,
            "name": instance.__str__(),
            "model": f"{instance._meta.app_label}.{instance._meta.model_name}",
        }


class LinkTypes(str, Enum):
    relational = "RE"
    static = "ST"


class MenuNodeLink(BaseModel):
    link_type: LinkTypes = LinkTypes.static
    static: Optional[str] = None
    content_type: Optional[ContentType] = None
    page: Annotated[Optional[AbstractPage], FieldSerializer(AbstractPageMinimalSerializer)] = None
    url_node: Optional[UrlNode] = None

    model_config = ConfigDict(
        json_schema_extra=conditional_schema(
            When(
                "link_type",
                equals=LinkTypes.static.value,
                controls=["static"],
                then={"required": ["static"]},
            ),
            When(
                "link_type",
                equals=LinkTypes.relational.value,
                controls=["url_node"],
            ),
            # content_type and page are auto-derived; hide them from the editor
            When("link_type", equals="__auto__", controls=["content_type", "page"]),
        )
    )

    @model_validator(mode="after")
    def derive_page_and_content_type(self):
        if self.link_type == LinkTypes.relational and self.url_node:
            url_node_id = getattr(self.url_node, "pk", self.url_node)
            url_node = UrlNode.objects.filter(pk=url_node_id).first()
            if url_node and url_node.page:
                self.page = url_node.page
                self.content_type = ContentType.objects.get_for_model(self.page.__class__)
        return self

    def get_url(self, request=None):
        if self.link_type == LinkTypes.relational:
            return isinstance(self.url_node, UrlNode) and self.url_node.routerlink
        elif self.link_type == LinkTypes.static:
            return self.static

    @computed_field
    @property
    def url(self) -> Optional[str]:
        return self.get_url()


class MenuNode(BaseModel):
    id: str = Field(default_factory=uuid4)
    meta: dict = {}
    nodes: List["MenuNode"] = []
    title: str = ""
    link: MenuNodeLink


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
        is_preview = (
            False if request is None else bool(request.GET.get("preview", False))
        )
        context.update({"menu": self, "is_preview": is_preview})
        return mark_safe(render_to_string(template_path, context, request))

    class defaultdict(dict):
        def __missing__(self, key):
            dict.__setitem__(self, key, Menu.objects.get_or_create(key=key)[0])
            return self[key]

    def __str__(self) -> str:
        return self.key
