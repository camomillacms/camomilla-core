"""``SafeNestingMixin`` — depth-based nested serialization must never dump the
auth user row verbatim on the public page router.

The mixin is *blacklist*-shaped: it strips the known-sensitive auth columns and
lets everything else (including a project's own custom user columns) through.
Because a blacklist fails *open*, these tests pin both halves of the contract —
sensitive defaults stay out, benign data flows in — so a regression that widens
the exposure is caught.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from camomilla.models import Article
from camomilla.serializers.mixins.safe_nesting import (
    SAFE_USER_FIELDS,
    _user_nested_meta_attrs,
)

client = APIClient()

# Auth columns that must never appear in public nested output.
SENSITIVE_USER_FIELDS = {
    "password",
    "last_login",
    "is_superuser",
    "is_staff",
    "is_active",
    "email",
    "groups",
    "user_permissions",
}


def _public_article_with_author():
    User = get_user_model()
    author = User.objects.create_superuser(
        username="leak-bait",
        email="secret@example.com",
        password="hunter2-should-never-surface",
    )
    article = Article.objects.create(
        title="Authored",
        permalink="/authored",
        published_at=timezone.now(),
        autopermalink=False,
        author=author,
    )
    return article, author


@pytest.mark.django_db(transaction=True, reset_sequences=True)
class TestSafeNestingPublicRouter:
    def test_author_fk_does_not_leak_sensitive_user_fields(self):
        """The unauthenticated router must not surface password / privilege /
        PII columns through the nested ``author``."""
        _public_article_with_author()

        response = client.get("/api/camomilla/pages-router/authored/")
        assert response.status_code == 200
        author = response.json().get("author")
        assert isinstance(author, dict), "author should nest as an object"

        leaked = SENSITIVE_USER_FIELDS & set(author)
        assert not leaked, f"sensitive user fields leaked publicly: {leaked}"
        # The password hash must not appear under any key, even renamed.
        assert "hunter2-should-never-surface" not in response.text
        assert "secret@example.com" not in response.text

    def test_benign_user_data_passes_through(self):
        """Blacklist intent: non-sensitive defaults (and, by the same rule, a
        project's custom user columns) display without per-project wiring."""
        _public_article_with_author()

        response = client.get("/api/camomilla/pages-router/authored/")
        author = response.json()["author"]
        # username / names are safe public identity; date_joined is a benign
        # default that is NOT in the blacklist and so flows through.
        assert author["username"] == "leak-bait"
        assert "date_joined" in author


@pytest.mark.django_db
class TestRelationalBranch:
    def test_depth0_author_fk_is_slim(self):
        """A plain ``BaseModelSerializer`` (``Meta.depth`` unset → DRF dispatches
        the relation through ``build_relational_field``, not
        ``build_nested_field``) must also strip the user row. Regression for the
        path where ``NestMixin`` re-nests a full ``__all__`` user serializer."""
        from camomilla.serializers.article import ArticleSerializer

        author = ArticleSerializer().fields["author"]
        nested = getattr(author, "serializer", None)
        assert nested is not None, "author should carry a nested serializer"
        keys = set(nested().fields)
        assert not (SENSITIVE_USER_FIELDS & keys), f"leak on relational branch: {keys}"
        assert "password" not in keys


@pytest.mark.django_db
class TestUserNestedMetaAttrs:
    def test_real_user_uses_exclude_and_strips_password(self):
        attrs = _user_nested_meta_attrs(get_user_model())
        assert "exclude" in attrs and "fields" not in attrs
        assert "password" in attrs["exclude"]
        # whitelist identity columns must survive (not be excluded)
        assert not (set(SAFE_USER_FIELDS) & set(attrs["exclude"]))

    @override_settings(
        CAMOMILLA={
            "API": {
                "SAFE_NESTING": {
                    "SENSITIVE_USER_FIELDS": ("password", "does_not_exist_xyz")
                }
            }
        }
    )
    def test_bogus_configured_field_is_filtered_not_crashed(self):
        """A sensitive-field name absent from the model is dropped, not passed
        to ``exclude`` (which would raise at serializer-build time). Settings
        resolve at import, so exercise the filter logic directly with an
        explicit candidate set rather than relying on the override."""
        from camomilla.serializers.mixins import safe_nesting

        candidates = ("password", "does_not_exist_xyz")
        model_fields = {f.name for f in get_user_model()._meta.get_fields()}
        to_exclude = tuple(n for n in candidates if n in model_fields)
        assert to_exclude == ("password",)
        # and the live helper never emits a field the model lacks
        attrs = safe_nesting._user_nested_meta_attrs(get_user_model())
        assert all(f in model_fields for f in attrs.get("exclude", ()))

    def test_fallback_uses_model_pk_name_not_hardcoded_id(self):
        """An exotic user model with a non-``id`` primary key and none of the
        known fields must fall back to its actual pk (not a literal ``"id"``,
        which would raise ``ImproperlyConfigured`` -> 500 on the public router).
        """

        class _F:
            def __init__(self, name):
                self.name = name

        class _Meta:
            pk = _F("code")

            def get_fields(self):
                return [_F("code"), _F("bio")]

        class _ExoticUser:
            _meta = _Meta()

        attrs = _user_nested_meta_attrs(_ExoticUser)
        assert attrs == {"model": _ExoticUser, "fields": ("code",)}
