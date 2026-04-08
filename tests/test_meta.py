from django.test import TransactionTestCase
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from camomilla.models import MetaType, MetaInstance
from example.website.models import SimpleRelationModel
from camomilla.meta import build_pydantic_model
from .utils.api import login_superuser


def _faq_schema():
    return [
        {"name": "question", "kind": "string", "required": True, "translated": True},
        {"name": "answer", "kind": "text", "required": True, "translated": True},
        {"name": "weight", "kind": "integer"},
    ]


def _nested_schema():
    return [
        {"name": "title", "kind": "string", "required": True},
        {
            "name": "items",
            "kind": "list",
            "children": [
                {"name": "label", "kind": "string", "required": True},
                {"name": "value", "kind": "number"},
            ],
        },
        {
            "name": "address",
            "kind": "group",
            "children": [
                {"name": "city", "kind": "string"},
                {"name": "zip", "kind": "string"},
            ],
        },
    ]


class MetaModelTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    # ---- model-level ----

    def test_compile_primitive_schema(self):
        mt = MetaType.objects.create(key="faq", name="FAQ", schema=_faq_schema())
        model_cls = build_pydantic_model(mt)
        instance = model_cls.model_validate(
            {
                "question": {"en": "What?", "it": "Cosa?"},
                "answer": {"en": "This.", "it": "Questo."},
                "weight": 3,
            }
        )
        assert instance.weight == 3
        assert instance.question["en"] == "What?"

    def test_required_field_missing_raises(self):
        mt = MetaType.objects.create(key="faq2", name="FAQ2", schema=_faq_schema())
        inst = MetaInstance(meta_type=mt, data={"weight": 1})
        with self.assertRaises(ValidationError):
            inst.full_clean()

    def test_nested_group_and_list(self):
        mt = MetaType.objects.create(key="card", name="Card", schema=_nested_schema())
        inst = MetaInstance(
            meta_type=mt,
            data={
                "title": "hello",
                "items": [{"label": "a", "value": 1.5}, {"label": "b"}],
                "address": {"city": "Rome"},
            },
        )
        inst.full_clean()
        inst.save()
        inst.refresh_from_db()
        assert inst.data["items"][0]["label"] == "a"
        assert inst.data["address"]["city"] == "Rome"

    def test_ref_field(self):
        related = SimpleRelationModel.objects.create(name="Foo")
        mt = MetaType.objects.create(
            key="hero",
            name="Hero",
            schema=[
                {
                    "name": "rel",
                    "kind": "ref",
                    "target_model": "website.SimpleRelationModel",
                    "required": True,
                },
                {"name": "caption", "kind": "string"},
            ],
        )
        inst = MetaInstance(meta_type=mt, data={"rel": related.pk, "caption": "hi"})
        inst.full_clean()
        inst.save()
        assert inst.data["rel"]["id"] == related.pk

    def test_schema_cache_invalidates_on_save(self):
        mt = MetaType.objects.create(
            key="evolving",
            name="Evolving",
            schema=[{"name": "a", "kind": "string"}],
        )
        m1 = build_pydantic_model(mt)
        assert "a" in m1.model_fields
        mt.schema = [{"name": "b", "kind": "integer"}]
        mt.save()
        m2 = build_pydantic_model(mt)
        assert "b" in m2.model_fields
        assert "a" not in m2.model_fields

    # ---- API ----

    def test_api_create_meta_type_and_instance(self):
        resp = self.client.post(
            "/api/camomilla/meta-types/",
            {"key": "faq", "name": "FAQ", "schema": _faq_schema()},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        mt_id = resp.data["id"]

        resp = self.client.post(
            "/api/camomilla/meta-instances/",
            {
                "meta_type": mt_id,
                "identifier": "first",
                "data": {
                    "question": {"en": "Q"},
                    "answer": {"en": "A"},
                },
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content

        # Invalid: missing required field
        resp = self.client.post(
            "/api/camomilla/meta-instances/",
            {"meta_type": mt_id, "data": {}},
            format="json",
        )
        assert resp.status_code == 400

    def test_api_schema_action(self):
        mt = MetaType.objects.create(key="faq", name="FAQ", schema=_faq_schema())
        resp = self.client.get(
            f"/api/camomilla/meta-instances/schema/?meta_type={mt.pk}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "properties" in body
        assert "question" in body["properties"]
