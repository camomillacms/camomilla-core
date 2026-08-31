"""Query-count guard for pages-router/changes — the same N+1 signal
django-debug-toolbar's SQL panel shows, but reproducible.

The endpoint serializes every public page in every language, so a per-node
query pattern explodes as pages × languages. We assert the MARGINAL query cost
per added page is bounded (no N+1), not a fixed total (which would rot as the
serializer graph changes)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from camomilla.models import Content, Page


def _seed(start, n, parent):
    ct = ContentType.objects.get_for_model(Page)
    for i in range(start, start + n):
        p = Page.objects.create(
            title=f"page-{i}",
            permalink=f"p{i}",
            published_at=timezone.now(),
            autopermalink=False,
            parent_page=parent,  # gives every page a breadcrumb ancestor
        )
        Content.objects.create(
            identifier="body", content=f"c{i}",
            content_type=ct, object_id=p.pk,
        )


def _measure():
    with CaptureQueriesContext(connection) as ctx:
        resp = Client().get("/api/camomilla/pages-router/changes")
        assert resp.status_code == 200
    return len(ctx.captured_queries), len(resp.json()["urls"])


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_changes_has_no_n_plus_one():
    root = Page.objects.create(
        title="root", permalink="root", published_at=timezone.now(), autopermalink=False
    )
    _seed(0, 10, root)
    q_small, u_small = _measure()

    _seed(10, 40, root)  # +40 pages
    q_large, u_large = _measure()

    marginal = (q_large - q_small) / (u_large - u_small)
    print(f"\nchanges endpoint: {q_small} q @ {u_small} urls → {q_large} q @ {u_large} urls "
          f"| marginal={marginal:.2f} q/url")
    # No N+1: the query count is bounded (independent of page count), so 40 extra
    # pages must add ~zero queries. Any per-page query would blow this.
    assert marginal < 0.3, f"N+1 regression: {marginal:.2f} queries per added page"
