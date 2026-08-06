"""Tests for the incremental static-build feed (``pages-router/changes``)
and the scheduled-publish sweep (``pages-router/publish-due``).

The load-bearing property is that the per-URL *content hash* — not any
timestamp — is what changes when a page's rendered payload changes, so a
djsuperadmin content edit (which bumps no ``date_updated_at``) is still
detected, while a page-external change (a menu) instead bumps the global
``epoch``.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Content, Menu, Page
from camomilla.models.page import UrlRedirect
from camomilla.models.site import SiteEpoch
from .utils.api import login_superuser

CHANGES_URL = "/api/camomilla/pages-router/changes"


def _changes():
    response = Client().get(CHANGES_URL)
    assert response.status_code == 200
    return response.json()


def _hash_for(body, path):
    return next((u["hash"] for u in body["urls"] if u["path"] == path), None)


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_public_pages_listed_drafts_excluded():
    Page.objects.create(
        title="Live", permalink="live", published_at=timezone.now(), autopermalink=False
    )
    Page.objects.create(title="Draft", permalink="draft", autopermalink=False)

    body = _changes()
    paths = {u["path"] for u in body["urls"]}
    assert "/live/" in paths
    assert "/draft/" not in paths  # published_at is None -> DRF -> not public


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_attached_content_edit_changes_hash_not_epoch():
    """A djsuperadmin-style edit to page-attached content bumps no page
    timestamp, yet MUST change that page's hash — and must NOT trigger a
    (full-rebuild) epoch bump."""
    page = Page.objects.create(
        title="Home", permalink="home", published_at=timezone.now(), autopermalink=False
    )
    block = Content.objects.create(
        identifier="body",
        content="before",
        content_type=ContentType.objects.get_for_model(Page),
        object_id=page.pk,
    )

    before = _changes()
    h_before = _hash_for(before, "/home/")
    assert h_before is not None

    block.content = "after"
    block.save()

    after = _changes()
    assert _hash_for(after, "/home/") != h_before  # hash is the rebuild authority
    assert after["epoch"] == before["epoch"]  # page-scoped edit != global fanout


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_menu_and_global_content_bump_epoch():
    assert SiteEpoch.current() is None
    Menu.objects.create(key="main")
    epoch_after_menu = SiteEpoch.current()
    assert epoch_after_menu is not None

    # A page-less (global) content block also fans out to every page.
    Content.objects.create(identifier="footer", content="c 2026")
    assert SiteEpoch.current() > epoch_after_menu


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_redirects_surfaced_as_public_paths():
    page = Page.objects.create(
        title="New", permalink="new-url", published_at=timezone.now(), autopermalink=False
    )
    UrlRedirect.objects.create(
        from_url="/old-url", to_url="/new-url", url_node=page.url_node, language_code="en"
    )
    body = _changes()
    froms = {r["from"] for r in body["redirects"]}
    assert "/old-url/" in froms
    assert all(r["status"] in (301, 302) for r in body["redirects"])


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_language_less_redirect_does_not_break_the_feed():
    """``UrlRedirect.language_code`` is nullable. A NULL row used to make
    ``public_path`` do ``"/" + None`` and take the WHOLE feed down with a
    TypeError — which stops the static build dead, since the manifest is
    step 2 of every build. A language-less redirect is not scoped to a
    language, so it gets the unprefixed path."""
    page = Page.objects.create(
        title="New", permalink="new-url", published_at=timezone.now(), autopermalink=False
    )
    UrlRedirect.objects.create(
        from_url="/legacy", to_url="/new-url", url_node=page.url_node, language_code=None
    )

    body = _changes()  # asserts 200 — used to be a 500
    assert "/legacy/" in {r["from"] for r in body["redirects"]}


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_publish_due_requires_staff():
    assert Client().post("/api/camomilla/pages-router/publish-due").status_code in (401, 403)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token " + login_superuser())
    response = client.post("/api/camomilla/pages-router/publish-due")
    assert response.status_code == 200
    assert "published" in response.json()
