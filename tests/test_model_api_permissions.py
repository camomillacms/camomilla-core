import pytest
from rest_framework.test import APIClient
from .utils.api import login_user, login_superuser, login_staff

client = APIClient()


@pytest.mark.django_db
def test_right_permissions():
    response = client.post("/api/models/test-model/", {"title": "test"}, format="json")
    assert response.status_code == 401
    token = login_user()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    response = client.post("/api/models/test-model/", {"title": "test"}, format="json")
    assert response.status_code == 403
    token = login_staff()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    response = client.post("/api/models/test-model/", {"title": "test"}, format="json")
    assert response.status_code == 403
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    response = client.post("/api/models/test-model/", {"title": "test"}, format="json")
    assert response.status_code == 201
    response = client.get("/api/models/test-model/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    response = client.get("/api/models/test-model/1/")
    assert response.status_code == 200
    response = client.patch(
        "/api/models/test-model/1/", {"title": "updated"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["title"] == "updated"
    response = client.delete("/api/models/test-model/1/")
    assert response.status_code == 204
    response = client.get("/api/models/test-model/")
    assert response.status_code == 200
    assert len(response.json()) == 0
    response = client.get("/api/models/test-model/1/")
    assert response.status_code == 404
    assert response.json() in [
        {"detail": "Not found."},
        {"detail": "No TestModel matches the given query."},
    ]
