from rest_framework import serializers
from camomilla.models import UrlNode
from camomilla.serializers.validators import UniquePermalinkValidator
from typing import TYPE_CHECKING
from structured.contrib.restframework import StructuredModelSerializer


if TYPE_CHECKING:
    from camomilla.models.page import AbstractPage


class AbstractPageMixin(StructuredModelSerializer, serializers.ModelSerializer):
    """
    This mixin is needed to serialize ``AbstractPage`` models. It provides
    permalink validation and the standard read-only lifecycle / breadcrumb
    fields. Use it as a base class for your serializer if you need to
    serialize custom ``AbstractPage`` models.

    URL localization inside ``template_data``:
        When a page declares its ``template_data`` as a typed schema
        (``StructuredJSONField`` with a pydantic schema), URL-bearing
        fields should be typed with :data:`camomilla.types.Permalink`.
        The type serializes itself to the active-language routerlink on
        the way out — no walk over free-form JSON happens here, and the
        stored value stays a raw permalink so writes round-trip safely.

        For pages that keep ``template_data`` as a raw ``JSONField``,
        render-time helpers are the supported path: ``{% localized_url %}``
        in Django templates, and the equivalent server-side resolution
        on the API consumer side (the astro integration ships one).
    """

    breadcrumbs = serializers.SerializerMethodField()
    routerlink = serializers.CharField(read_only=True)
    template_file = serializers.SerializerMethodField()
    # Visibility flags — fine to expose anywhere, including the public
    # route. Read-only and computed from ``published_at`` / ``deleted_at``.
    status = serializers.CharField(read_only=True)
    is_public = serializers.BooleanField(read_only=True)
    # ``has_draft`` / ``has_scheduled_draft`` are NOT declared here — those
    # are author-facing observability flags and the ``PageViewSet.preview``
    # action attaches them via ``_draft_overlay`` when relevant. Keeping
    # them off the default serializer prevents the public ``pages-router``
    # from revealing whether a page has pending edits.

    # How many ancestor levels to eager-load for breadcrumbs (bounded so the
    # join count stays constant). Override on a subclass if you nest deeper.
    EAGER_BREADCRUMB_DEPTH = 5

    @classmethod
    def setup_eager_loading(cls, queryset, context=None):
        """Eager-load the routing chain. Page list/detail reads otherwise fire
        a ``url_node`` query per row (for routerlink/permalink/is_public) and a
        ``parent_page`` + ``url_node`` query per breadcrumb ancestor. We
        ``select_related`` the page's own ``url_node`` plus a bounded ancestor
        chain (each with its ``url_node``) so those reads come from cache.

        Hooked automatically by ``SetupEagerLoadingMixin.optimize_qs``, so every
        page viewset (``PageViewSet`` and any downstream custom ``AbstractPage``
        viewset) inherits it with no per-viewset wiring. Same fast path as
        ``PageQuerySet.with_urls``.
        """
        from camomilla.managers.pages import page_routing_relations

        return queryset.select_related(
            *page_routing_relations(cls.EAGER_BREADCRUMB_DEPTH)
        )

    def get_template_file(self, instance: "AbstractPage"):
        return instance.get_template_path()

    def get_breadcrumbs(self, instance: "AbstractPage"):
        return instance.breadcrumbs

    @property
    def translation_fields(self):
        return super().translation_fields + ["permalink"]

    def get_default_field_names(self, *args):
        from camomilla.serializers.mixins.translation import RemoveTranslationsMixin

        default_fields = super().get_default_field_names(*args)
        filtered_fields = getattr(self, "filtered_fields", [])
        if len(filtered_fields) > 0:
            return filtered_fields
        if RemoveTranslationsMixin in self.__class__.__bases__:  # noqa: E501
            return default_fields
        return list(
            set(
                [f for f in default_fields if f != "url_node"]
                + UrlNode.LANG_PERMALINK_FIELDS
                + ["permalink"]
            )
        )

    def build_field(self, field_name, info, model_class, nested_depth):
        if field_name in UrlNode.LANG_PERMALINK_FIELDS + ["permalink"]:
            return serializers.CharField, {
                "required": False,
                "allow_blank": True,
            }
        return super().build_field(field_name, info, model_class, nested_depth)

    def get_validators(self):
        return super().get_validators() + [UniquePermalinkValidator()]
