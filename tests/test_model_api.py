import pytest
from rest_framework.test import APIClient
from .fixtures import load_json_fixture
from .utils.api import login_superuser
from example.website.models import SimpleRelationModel


client = APIClient()


@pytest.fixture(autouse=True)
def init_test():
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    SimpleRelationModel.objects.bulk_create(
        [SimpleRelationModel(name=f"test{i}") for i in range(1, 10)]
    )


@pytest.mark.django_db
def test_simple_relation_model_api_endpoint():
    response = client.get("/api/models/simple-relation-model/")
    assert response.status_code == 200
    assert len(response.json()) == 9
    response = client.get("/api/models/simple-relation-model/1/")
    assert response.status_code == 200
    assert response.json()["name"] == "test1"
    response = client.patch(
        "/api/models/simple-relation-model/1/", {"name": "updated"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["name"] == "updated"
    response = client.delete("/api/models/simple-relation-model/1/")
    assert response.status_code == 204
    response = client.get("/api/models/simple-relation-model/")
    assert response.status_code == 200
    assert len(response.json()) == 8
    response = client.get("/api/models/simple-relation-model/1/")
    assert response.status_code == 404
    assert response.json() in [
        {"detail": "Not found."},
        {"detail": "No SimpleRelationModel matches the given query."},
    ]


@pytest.mark.django_db
def test_test_model_api_endpoint():
    response = client.get("/api/models/test-model/")
    assert response.status_code == 200
    assert response.json() == []
    test_model_data = load_json_fixture("test-model-api.json")
    response = client.post("/api/models/test-model/", test_model_data, format="json")
    assert response.status_code == 201
    assert response.json()["title"] == test_model_data["title"]
    assert (
        response.json()["structured_data"]["name"]
        == test_model_data["structured_data"]["name"]
    )
    assert (
        response.json()["structured_data"]["age"]
        == test_model_data["structured_data"]["age"]
    )
    assert (
        response.json()["structured_data"]["child"]["name"]
        == test_model_data["structured_data"]["child"]["name"]
    )
    assert (
        response.json()["structured_data"]["childs"][0]["name"]
        == test_model_data["structured_data"]["childs"][0]["name"]
    )
    assert (
        response.json()["structured_data"]["fk_field"]["id"]
        == test_model_data["structured_data"]["fk_field"]["id"]
    )
    assert (
        response.json()["structured_data"]["qs_field"][0]["id"]
        == test_model_data["structured_data"]["qs_field"][0]["id"]
    )
    response = client.get("/api/models/test-model/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    response = client.get("/api/models/test-model/1/")
    assert response.status_code == 200
    assert response.json()["title"] == test_model_data["title"]
    assert (
        response.json()["structured_data"]["name"]
        == test_model_data["structured_data"]["name"]
    )
    assert (
        response.json()["structured_data"]["age"]
        == test_model_data["structured_data"]["age"]
    )
    assert (
        response.json()["structured_data"]["child"]["name"]
        == test_model_data["structured_data"]["child"]["name"]
    )
    assert (
        response.json()["structured_data"]["childs"][0]["name"]
        == test_model_data["structured_data"]["childs"][0]["name"]
    )
    assert (
        response.json()["structured_data"]["fk_field"]["id"]
        == test_model_data["structured_data"]["fk_field"]["id"]
    )
    assert (
        response.json()["structured_data"]["qs_field"][0]["id"]
        == test_model_data["structured_data"]["qs_field"][0]["id"]
    )
    response = client.patch(
        "/api/models/test-model/1/", {"title": "updated"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["title"] == "updated"
