import pytest
from django.conf import settings
from rest_framework.test import APIClient

from .utils.api import login_superuser

client = APIClient()

SITE_CODES = [code for code, _ in settings.LANGUAGES]


def _auth():
    client.credentials(HTTP_AUTHORIZATION="Token " + login_superuser())


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_options_exposes_lang_info_for_a_translatable_model():
    """
    OPTIONS is the only source: `lang_info` describes the model, and a "create
    new" form has no record to retrieve.
    """
    _auth()
    info = client.options("/api/camomilla/articles/").json()["lang_info"]

    assert info["default"] == settings.LANGUAGE_CODE
    assert info["translatable"] is True
    # Flat codes, NOT {id, name} objects: clients key translations by code.
    assert info["languages"] == SITE_CODES
    assert all(isinstance(code, str) for code in info["languages"])
    assert "title" in info["translatable_fields"]


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_options_reports_a_non_translatable_model():
    """
    Why this lives on the model and not the site: a multilingual site can still
    expose models nobody registered for translation. Advertising the site's
    languages there makes a client render tabs whose values the backend drops.
    """
    _auth()
    info = client.options("/api/camomilla/users/").json()["lang_info"]

    assert info["translatable"] is False
    assert info["languages"] == []
    assert info["translatable_fields"] == []
    # The site is still multilingual — that fact just does not apply here.
    assert info["site_languages"] == SITE_CODES


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_records_do_not_carry_lang_info():
    """
    It used to ride along on every retrieve. That duplicated metadata into data
    and could drift from OPTIONS; OPTIONS is now the single source.
    """
    _auth()
    created = client.post("/api/camomilla/tags/", {"name_en": "Tag"})
    assert created.status_code == 201

    detail = client.get(f"/api/camomilla/tags/{created.json()['id']}/").json()
    assert "lang_info" not in detail

    rows = client.get("/api/camomilla/tags/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows and all("lang_info" not in row for row in rows)


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_translatable_fields_match_the_serializer_not_the_registry():
    """
    Page/Article serializers append `permalink` to translation_fields, and
    modeltranslation's registry has never heard of it. A client trusting the
    registry writes permalink at the top level, nest_to_plain pops it as a
    translated field, and the edit vanishes silently — on a CMS page's most
    important field.
    """
    _auth()
    for endpoint in ("pages", "articles"):
        info = client.options(f"/api/camomilla/{endpoint}/").json()["lang_info"]
        assert "permalink" in info["translatable_fields"], endpoint
        assert "title" in info["translatable_fields"], endpoint


# ─── Flat form schema on OPTIONS ─────────────────────────────────────────────


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_options_publishes_a_flat_form_schema():
    """JSON Schema shaped so a form generator can consume it directly."""
    _auth()
    schema = client.options("/api/camomilla/articles/").json()["schema"]

    assert schema["type"] == "object"
    assert isinstance(schema["properties"], dict)
    # `required` is a root-level ARRAY, as JSON Schema wants — not a per-field bool.
    assert isinstance(schema.get("required", []), list)
    assert schema["properties"]["title"]["type"] == "string"


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_form_schema_has_no_translations_envelope():
    """
    The envelope is transport, not a field. Rendered as a control it is either a
    text input bound to the whole {it,en} object — one keystroke wipes every
    language — or an unknown object type. Each field appears once instead.
    """
    _auth()
    schema = client.options("/api/camomilla/articles/").json()["schema"]
    props = schema["properties"]

    assert "translations" not in props
    # ...and no duplicate per-language twins either.
    assert not [k for k in props if k.endswith(("_it", "_en"))]


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_form_schema_flags_translatable_fields():
    _auth()
    for endpoint in ("articles", "pages"):
        props = client.options(f"/api/camomilla/{endpoint}/").json()["schema"][
            "properties"
        ]
        assert props["title"].get("translatable") is True, endpoint
        # permalink is added by the page serializer, not by modeltranslation.
        assert props["permalink"].get("translatable") is True, endpoint
        # A non-translated field must NOT be flagged.
        assert "translatable" not in props["id"], endpoint


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_form_schema_of_a_non_translatable_model_flags_nothing():
    _auth()
    props = client.options("/api/camomilla/users/").json()["schema"]["properties"]

    assert "translations" not in props
    assert not [k for k, v in props.items() if v.get("translatable")]


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_form_schema_carries_labels_and_readonly():
    """
    DRF's OpenAPI drops labels; a generated form needs them, and
    useFormFromSchema reads `title`. read_only must survive too, or the form
    offers editable inputs the backend ignores.
    """
    _auth()
    props = client.options("/api/camomilla/articles/").json()["schema"]["properties"]

    assert props["title"].get("title")
    assert props["id"].get("readOnly") is True


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_options_publishes_the_translation_accessor():
    """
    Configurable setting. A client hardcoding "translations" on a project that
    changed it writes to a key nest_to_plain never reads, dropping every
    translation on save with nothing to detect it.
    """
    _auth()
    lang_info = client.options("/api/camomilla/articles/").json()["lang_info"]
    assert lang_info["accessor"] == "translations"


# ─── Relations ───────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_relations_are_described_as_relations():
    """
    DRF maps a PrimaryKeyRelatedField to {"type": "integer"} — a number input
    asking an editor for a database id. Worse, SimpleMetadata renders FKs, M2Ms,
    JSONFields and SerializerMethodFields identically, so a client cannot even
    tell them apart.
    """
    _auth()
    props = client.options("/api/camomilla/articles/").json()["schema"]["properties"]

    assert props["author"]["type"] == "relation"
    assert props["author"]["model"] == "auth.User"
    assert props["author"]["multiple"] is False
    assert props["author"]["endpoint"] == "/api/camomilla/users/"

    # M2M carries the same keys, differing only by `multiple`.
    assert props["tags"]["type"] == "relation"
    assert props["tags"]["model"] == "camomilla.Tag"
    assert props["tags"]["multiple"] is True
    assert props["tags"]["endpoint"] == "/api/camomilla/tags/"


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_media_relations_publish_the_model_not_a_widget():
    """
    Choosing a media picker over a generic autocomplete is the client's call.
    The API says what the thing IS; `model` is the hook for that decision.
    """
    _auth()
    props = client.options("/api/camomilla/articles/").json()["schema"]["properties"]

    for key in ("og_image", "highlight_image"):
        assert props[key]["type"] == "relation", key
        assert props[key]["model"] == "camomilla.Media", key
        assert props[key]["endpoint"] == "/api/camomilla/media/", key


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_endpoints_are_reversed_not_string_built():
    """
    The routers are mounted under a prefix this code has no business hardcoding.
    Every endpoint must therefore start at the project's real mount point.
    """
    _auth()
    props = client.options("/api/camomilla/pages/").json()["schema"]["properties"]
    endpoints = [v["endpoint"] for v in props.values() if v.get("endpoint")]

    assert endpoints, "expected at least one relation on Page"
    assert all(e.startswith("/api/camomilla/") and e.endswith("/") for e in endpoints)


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_unbounded_text_is_marked_multiline():
    """
    A Django TextField becomes an unbounded CharField, so a generator's usual
    "maxLength > 255 means multiline" heuristic never fires and an article body
    renders as a single-line input. DRF already knows (it sets a textarea style
    for TextField); this makes that explicit in the schema.
    """
    _auth()
    props = client.options("/api/camomilla/articles/").json()["schema"]["properties"]

    assert props["content"]["format"] == "textarea"
    assert props["description"]["format"] == "textarea"
    # A bounded CharField must NOT be marked.
    assert "format" not in props["title"]
    # An existing format is never clobbered.
    assert props["published_at"]["format"] == "date-time"
