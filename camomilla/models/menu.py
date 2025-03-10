from enum import Enum
from uuid import uuid4
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils.safestring import mark_safe
from pydantic import (
    Field,
    SerializationInfo,
    computed_field,
    model_serializer,
)
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField
from camomilla.models.page import UrlNode, AbstractPage
from typing import Optional, Union, Callable, List
from django.db.models.base import Model as DjangoModel


class LinkTypes(str, Enum):
    relational = "RE"
    static = "ST"


class MenuNodeLink(BaseModel):
    link_type: LinkTypes = LinkTypes.static
    static: str = None
    content_type: ContentType = None
    page: AbstractPage = None
    url_node: UrlNode = None

    @model_serializer(mode="wrap", when_used="json")
    def update_relational(self, handler: Callable, info: SerializationInfo):
        if self.link_type == LinkTypes.relational:
            if self.content_type and self.page:
                if isinstance(self.page, DjangoModel) and not self.page._meta.abstract:
                    self.content_type = ContentType.objects.get_for_model(
                        self.page.__class__
                    )
                ctype_id = getattr(self.content_type, "pk", self.content_type)
                page_id = getattr(self.page, "pk", self.page)
                c_type = ContentType.objects.filter(pk=ctype_id).first()
                model = c_type and c_type.model_class()
                page = model and model.objects.filter(pk=page_id).first()
                self.url_node = page and page.url_node
            elif self.url_node:
                url_node_id = getattr(self.url_node, "pk", self.url_node)
                self.page = UrlNode.objects.filter(pk=url_node_id).first().page
                self.content_type = ContentType.objects.get_for_model(
                    self.page.__class__
                )
        return handler(self)

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
    key = models.CharField(max_length=200, unique=True, editable=False)
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
