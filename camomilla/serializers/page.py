from camomilla.models.page import UrlNode
from camomilla.serializers.mixins import AbstractPageMixin
from camomilla.models import Content, Page
from camomilla.serializers.base import BaseModelSerializer
from rest_framework import serializers
from django.utils.translation import get_language
from django.contrib.contenttypes.models import ContentType

from camomilla.serializers.utils import (
    build_standard_model_serializer,
    get_standard_bases,
)


class ContentSerializer(BaseModelSerializer):
    class Meta:
        model = Content
        fields = "__all__"


class PageSerializer(AbstractPageMixin, BaseModelSerializer):
    class Meta:
        model = Page
        fields = "__all__"


class UrlNodeSerializer(BaseModelSerializer):
    is_public = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    indexable = serializers.SerializerMethodField()

    class Meta:
        model = UrlNode
        fields = ("id", "permalink", "status", "indexable", "is_public")

    def get_is_public(self, instance: UrlNode):
        return instance.page.is_public

    def get_status(self, instance: UrlNode):
        return instance.page.status

    def get_indexable(self, instance: UrlNode):
        return instance.page.indexable


class RouteSerializer(UrlNodeSerializer):
    alternates = serializers.SerializerMethodField()
    contents = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()

    def get_language(self, instance: UrlNode):
        return get_language()

    def get_alternates(self, instance: UrlNode):
        return instance.page.alternate_urls()

    def get_content_type(self, instance: UrlNode):
        return ContentType.objects.get_for_model(type(instance.page)).id

    def get_contents(self, instance: UrlNode):
        related = getattr(instance.page, "contents", None)
        if related is None:
            return {}
        return {c.identifier: {"id": c.id, "content": c.content} for c in related.all()}

    def to_representation(self, instance: UrlNode):
        standard_serializer = instance.page.get_serializer()
        model_serializer = build_standard_model_serializer(
            instance.page.__class__,
            depth=10,
            bases=(standard_serializer,) + get_standard_bases(),
        )
        return {
            **super().to_representation(instance),
            **model_serializer(instance.page, context=self.context).data,
        }

    class Meta:
        model = UrlNode
        fields = "__all__"
