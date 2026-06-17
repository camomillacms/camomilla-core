"""UrlNode lean-default queryset + opt-in ``with_lifecycle`` / ``with_page``.

Pins both the performance contract (the default queryset is join-free; the page
data is opt-in) and the per-language correctness of the serializers that read
lifecycle / ``indexable`` off a UrlNode.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone, translation
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from camomilla.models import Article, Page, UrlNode
from camomilla.serializers.page import RouteSerializer, UrlNodeSerializer
from camomilla.utils import set_nofallbacks


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class TestUrlNodeLeanDefault:
    def test_default_queryset_is_join_free(self):
        """The permalink / uniqueness hot path pays no page-table joins."""
        sql = str(UrlNode.objects.filter(permalink="/x").query)
        assert sql.count("LEFT OUTER JOIN") == 0
        assert "is_public" not in sql.lower()

    def test_with_lifecycle_opts_into_the_annotation(self):
        sql = str(UrlNode.objects.with_lifecycle().filter(permalink="/x").query)
        assert sql.count("LEFT OUTER JOIN") > 0
        assert "is_public" in sql.lower()

    def test_with_page_reuses_lifecycle_joins(self):
        """Chaining the two adds no joins — with_page only widens the SELECT."""
        page_only = str(UrlNode.objects.with_page().query).count("LEFT OUTER JOIN")
        chained = str(
            UrlNode.objects.with_lifecycle().with_page().query
        ).count("LEFT OUTER JOIN")
        assert chained == page_only


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class TestWithPageCrossModel:
    def test_resolves_each_concrete_type_with_zero_followup_queries(self):
        now = timezone.now()
        page = Page.objects.create(
            title="P", permalink="/p", published_at=now, autopermalink=False
        )
        article = Article.objects.create(
            title="A", permalink="/a", published_at=now, autopermalink=False
        )
        nodes = {
            n.pk: n
            for n in UrlNode.objects.with_page().filter(
                pk__in=[page.url_node_id, article.url_node_id]
            )
        }
        with CaptureQueriesContext(connection) as captured:
            resolved = {
                nodes[page.url_node_id].page.__class__,
                nodes[article.url_node_id].page.__class__,
            }
        assert resolved == {Page, Article}
        assert len(captured) == 0  # cross-model dispatch, no per-node page fetch

    def test_sitemap_style_iteration_is_o1_queries(self):
        now = timezone.now()
        for i in range(5):
            Page.objects.create(
                title=f"P{i}", permalink=f"/p{i}", published_at=now, autopermalink=False
            )
        qs = UrlNode.objects.with_lifecycle().with_page().filter(is_public=True)
        with CaptureQueriesContext(connection) as captured:
            klasses = [n.page.__class__ for n in qs]
        assert len(klasses) == 5
        assert len(captured) == 1  # one query, no N+1 on .page


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class TestSerializerLanguageCorrectness:
    def _bilingual_page(self):
        """Public in EN and IT; indexable EN=True / IT=False."""
        now = timezone.now()
        page = Page.objects.create(title="P", permalink="/p", autopermalink=False)
        for lang in ("en", "it"):
            set_nofallbacks(page, "published_at", now, language=lang)
        set_nofallbacks(page, "indexable", True, language="en")
        set_nofallbacks(page, "indexable", False, language="it")
        page.save()
        return page

    def test_urlnode_serializer_indexable_is_per_language(self):
        page = self._bilingual_page()
        # The with_lifecycle() annotation is resolved at build time, so build
        # and serialize under the same active language (what the callers do).
        for lang, expected in (("en", True), ("it", False)):
            with translation.override(lang):
                node = UrlNode.objects.with_lifecycle().get(pk=page.url_node_id)
                assert UrlNodeSerializer(node).data["indexable"] is expected

    def test_route_serializer_indexable_not_shadowed_by_page_base_column(self):
        """RouteSerializer merges the full page serialization on top; its flat
        base-column ``indexable`` must NOT shadow the per-language value."""
        page = self._bilingual_page()
        request = Request(APIRequestFactory().get("/p"))
        for lang, expected in (("en", True), ("it", False)):
            with translation.override(lang):
                node = UrlNode.objects.with_page().get(pk=page.url_node_id)
                data = RouteSerializer(node, context={"request": request}).data
                assert data["indexable"] is expected
