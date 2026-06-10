"""Pydantic-compatible types for use inside user-defined ``template_data``
schemas (``structured-json-field``). The point of this module is to give
schema authors typed primitives that *know how to serialize themselves*,
so the page serializer never has to walk an arbitrary JSON tree looking
for things to localize, fix up, or otherwise transform.

If you find yourself reaching for a post-hoc walk over ``template_data``
to mutate values on the way out, prefer adding a typed primitive here
and let pydantic do the work at the field boundary.
"""

from enum import Enum
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from pydantic import ConfigDict, computed_field, model_validator
from rest_framework import serializers
from structured.pydantic.conditionals import When, conditional_schema
from structured.pydantic.fields.serializer import FieldSerializer
from structured.pydantic.models import BaseModel
from typing_extensions import Annotated

# Eager imports — ``camomilla.types`` is imported lazily from any consumer
# (user models, the menu module, the seed). By the time any of those run,
# Django has already loaded ``camomilla.models.page`` (it's an in-package
# import that ``camomilla.models.__init__`` triggers before reaching the
# menu module). Importing eagerly here keeps the pydantic schema simple
# — no forward refs to rebuild — and makes the dependency direction
# explicit: types builds on models, never the reverse.
from camomilla.models.page import AbstractPage, UrlNode


class _AbstractPageMinimalSerializer(serializers.Serializer):
    """Compact representation for the ``page`` derived field on a
    :class:`Permalink` — just enough for an editor or a frontend to
    identify the target without dragging in the whole page payload.
    """

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "name": instance.__str__(),
            "model": f"{instance._meta.app_label}.{instance._meta.model_name}",
        }


class LinkTypes(str, Enum):
    """Discriminator for the two branches of :class:`Permalink`.

    * ``relational`` — points at an internal page via its ``UrlNode``.
      Survives renames (the FK tracks the row, not the URL string) and
      resolves to the active-language routerlink at read time.
    * ``static`` — free-form URL string for everything that isn't an
      internal camomilla page: external links, ``mailto:``, ``tel:``,
      in-page anchors.
    """

    relational = "RE"
    static = "ST"


class Permalink(BaseModel):
    """Typed link primitive for ``template_data`` fields.

    Replaces bare-string URL fields with a small polymorphic struct that
    can hold *either* a foreign-key reference to a camomilla ``UrlNode``
    (the editor picks a real page) *or* a plain string (any external
    URL). Same shape — and same editor UX — used by ``MenuNode.link``,
    which is now just an alias for this type.

    Why this exists:

    * **Referential integrity.** A relational link holds the ``UrlNode``
      PK, not a string. Renaming the target page changes the public
      URL but the link still points at the same row. Deleting the
      target nulls the FK rather than silently breaking the string.
    * **Per-language routerlinks on the way out.** The ``url``
      ``computed_field`` returns ``url_node.routerlink``, which honors
      Django's ``i18n_patterns`` + ``APPEND_SLASH``. On /it/ a link to
      the about page emits ``/it/about/`` without any consumer-side
      i18n logic.
    * **No round-trip corruption.** Storage is JSON shaped exactly as
      the editor entered it; ``url`` is *derived*, never persisted.
      Writing the response back as-is just stores the same struct
      again (the computed field is read-only).

    Authoring:

        from typing import Optional
        from camomilla.types import Permalink, LinkTypes
        from structured.pydantic.models import BaseModel

        class HeroBlock(BaseModel):
            headline: str = ""
            cta_label: str = ""
            cta_url: Optional[Permalink] = None

        # In code / fixtures:
        cta = Permalink(link_type=LinkTypes.relational, url_node=node)
        cta = Permalink(link_type=LinkTypes.static, static="https://example.com")
    """

    # Discriminator. ``static`` is the safer default for hand-rolled
    # fixtures; the admin UI flips this when the editor picks a page.
    link_type: LinkTypes = LinkTypes.static
    # Free-form URL string for non-camomilla targets (externals, mailto,
    # tel, anchors). Honored only when ``link_type == static``.
    static: Optional[str] = None
    # Auto-derived from ``url_node`` for relational links — exposed so
    # frontends can identify the target's model / app without a second
    # API round-trip. Editors don't set these directly.
    content_type: Optional[ContentType] = None
    page: Annotated[
        Optional[AbstractPage],
        FieldSerializer(_AbstractPageMinimalSerializer),
    ] = None
    # The foreign key. Stores the ``UrlNode`` PK; pydantic + structured
    # rehydrate it to a model instance on read so ``url_node.routerlink``
    # works without a manual lookup.
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
            # ``content_type`` / ``page`` are derived — hide from the editor.
            When("link_type", equals="__auto__", controls=["content_type", "page"]),
        )
    )

    @model_validator(mode="after")
    def _derive_page_and_content_type(self):
        """Populate the derived ``page`` / ``content_type`` from
        ``url_node`` after validation. Editors only set ``url_node``;
        the rest follows from it.
        """
        if self.link_type == LinkTypes.relational and self.url_node:
            # Re-resolve via DB so an in-memory ``UrlNode(pk=...)`` placeholder
            # (e.g. from a JSON payload) gets a fully-hydrated row.
            url_node_id = getattr(self.url_node, "pk", self.url_node)
            url_node = UrlNode.objects.filter(pk=url_node_id).first()
            if url_node and url_node.page:
                self.page = url_node.page
                self.content_type = ContentType.objects.get_for_model(
                    self.page.__class__
                )
        return self

    def get_url(self, request=None) -> Optional[str]:
        """Resolve to an output URL. Relational links go through
        ``UrlNode`` (language-aware via ``i18n_patterns`` + ``APPEND_SLASH``);
        static links pass the editor's string through verbatim.

        Pass ``request`` to get an absolute URI (scheme + host) for
        relational links — useful from a template tag or a serializer
        ``to_representation`` that has the request in context. Without a
        request the relational URL is root-relative (the safe default for
        a headless API whose host may differ from the frontend's).
        """
        if self.link_type == LinkTypes.relational:
            if not isinstance(self.url_node, UrlNode):
                return None
            return self.url_node.get_routerlink(request=request)
        if self.link_type == LinkTypes.static:
            return self.static
        return None

    @computed_field
    @property
    def url(self) -> Optional[str]:
        """Read-only ``url`` field that surfaces in JSON responses with
        the already-localized URL. Consumers should bind ``href`` to
        this, never to ``static`` directly.

        Root-relative by construction — a ``computed_field`` can't reach
        the serialization context, so there's no request here to build an
        absolute URI from. When you need an absolute link (sitemaps,
        emails, server-rendered templates), call :meth:`get_url` with the
        request instead of reading this field.
        """
        return self.get_url()
