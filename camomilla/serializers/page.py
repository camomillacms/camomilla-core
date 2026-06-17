from camomilla.models.page import UrlNode
from camomilla.serializers.mixins import AbstractPageMixin
from camomilla.models import Content, Page
from camomilla.serializers.base import BaseModelSerializer
from camomilla.utils import get_nofallbacks
from rest_framework import serializers

from camomilla.serializers.utils import (
    build_standard_model_serializer,
    get_standard_bases,
)


_MISSING = object()


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

    def _annotation_or_page(self, instance: UrlNode, field_name: str, page_value):
        """Prefer the ``with_lifecycle()`` annotation (cheap, present on the
        search path); otherwise fall back to the page (present via
        ``with_page()`` on the router path). The fallback must be
        per-language-correct, so it goes through the page property /
        ``get_nofallbacks`` rather than the bare base column."""
        value = getattr(instance, field_name, _MISSING)
        if value is not _MISSING:
            return value
        return page_value(instance.page)

    def get_is_public(self, instance: UrlNode):
        # page.is_public derives from get_nofallbacks(published_at/deleted_at).
        return self._annotation_or_page(instance, "is_public", lambda p: p.is_public)

    def get_status(self, instance: UrlNode):
        return self._annotation_or_page(instance, "status", lambda p: p.status)

    def get_indexable(self, instance: UrlNode):
        # ``indexable`` is translatable; the bare ``page.indexable`` descriptor
        # is fallback-y and can return the default-language value, so read the
        # active-language column explicitly.
        return self._annotation_or_page(
            instance, "indexable", lambda p: get_nofallbacks(p, "indexable")
        )


class RouteSerializer(UrlNodeSerializer):
    alternates = serializers.SerializerMethodField()

    def get_alternates(self, instance: UrlNode):
        return instance.page.alternate_urls()

    def to_representation(self, instance: UrlNode):
        page = instance.page
        node_data = super().to_representation(instance)
        standard_serializer = page.get_serializer()
        model_serializer = build_standard_model_serializer(
            page.__class__,
            depth=10,
            bases=(standard_serializer,) + get_standard_bases(),
        )
        data = {
            **node_data,
            **model_serializer(page, context=self.context).data,
        }
        # The page model serializer emits flat base-column status / is_public /
        # indexable that are NOT per-language-correct and would otherwise shadow
        # the UrlNode-derived values; re-assert the correct ones.
        for key in ("status", "is_public", "indexable"):
            if key in node_data:
                data[key] = node_data[key]
        return data

    class Meta:
        model = UrlNode
        fields = "__all__"
