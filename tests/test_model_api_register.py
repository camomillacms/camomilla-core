import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from example.website.models import TestModel


class ModelAPiRegisterTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    @pytest.mark.django_db
    def test_model_api_register_access(self):
        client = APIClient()
        response = client.post("/api/models/test-model/")
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_model_api_register_crud(self):
        # Create test model 1
        response = self.client.post(
            "/api/models/test-model/", {"title": "title_test_model_1"}, format="json"
        )
        assert response.status_code == 201
        assert len(TestModel.objects.all()) == 1
        test_model = TestModel.objects.first()
        assert test_model.id == 1
        assert test_model.title == "title_test_model_1"

        # Create test model 2
        response = self.client.post(
            "/api/models/test-model/", {"title": "title_test_model_2"}, format="json"
        )
        assert response.status_code == 201
        assert len(TestModel.objects.all()) == 2
        test_model = TestModel.objects.last()
        assert test_model.id == 2
        assert test_model.title == "title_test_model_2"

        # Update test model 2
        response = self.client.patch(
            "/api/models/test-model/2/",
            {
                "title": "title_test_model_2_updated",
            },
            format="json",
        )
        assert response.status_code == 200
        assert len(TestModel.objects.all()) == 2
        test_model = TestModel.objects.last()
        assert test_model.id == 2
        assert test_model.title == "title_test_model_2_updated"

        # Read test model 2
        response = self.client.get("/api/models/test-model/2/")
        assert response.status_code == 200
        assert response.json()["id"] == 2
        assert response.json()["title"] == "title_test_model_2_updated"

        # Read test models
        response = self.client.get("/api/models/test-model/")
        assert response.status_code == 200
        assert response.json()[0]["id"] == 2
        assert response.json()[0]["title"] == "title_test_model_2_updated"
        assert response.json()[1]["id"] == 1
        assert response.json()[1]["title"] == "title_test_model_1"

        # Delete page
        response = self.client.delete("/api/models/test-model/2/")
        assert response.status_code == 204
        assert len(TestModel.objects.all()) == 1
        test_model = TestModel.objects.last()
        assert test_model.id == 1
        assert test_model.title == "title_test_model_1"

    @pytest.mark.django_db
    def test_model_api_register_listing(self):
        # Create test model 1
        response = self.client.post(
            "/api/models/test-model/", {"title": "title_test_model_1"}, format="json"
        )
        assert response.status_code == 201

        # Create test model 2
        response = self.client.post(
            "/api/models/test-model/", {"title": "title_test_model_2"}, format="json"
        )
        assert response.status_code == 201

        # Create test model 3
        response = self.client.post(
            "/api/models/test-model/", {"title": "title_test_model_3"}, format="json"
        )
        assert response.status_code == 201

        # Simple Response
        response = self.client.get("/api/models/test-model/")
        assert response.status_code == 200
        assert len(response.json()) == 3
        assert response.json()[0]["id"] == 3
        assert response.json()[1]["id"] == 2
        assert response.json()[2]["id"] == 1

        # Pagination
        response = self.client.get("/api/models/test-model/?items=2")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2
        assert response.json()["items"][0]["id"] == 3
        assert response.json()["items"][1]["id"] == 2
        assert response.json()["paginator"]["count"] == 3
        assert response.json()["paginator"]["page"] == 1
        assert response.json()["paginator"]["has_next"] == True
        assert response.json()["paginator"]["has_previous"] == False
        assert response.json()["paginator"]["pages"] == 2
        assert response.json()["paginator"]["page_size"] == 2

        response = self.client.get("/api/models/test-model/?items=2&page=2")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["id"] == 1
        assert response.json()["paginator"]["count"] == 3
        assert response.json()["paginator"]["page"] == 2
        assert response.json()["paginator"]["has_next"] == False
        assert response.json()["paginator"]["has_previous"] == True
        assert response.json()["paginator"]["pages"] == 2
        assert response.json()["paginator"]["page_size"] == 2

        # Filtering
        response = self.client.get(
            "/api/models/test-model/?fltr=title=title_test_model_2"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == 2
        assert response.json()[0]["title"] == "title_test_model_2"

        response = self.client.get("/api/models/test-model/?fltr=title=not_real_title")
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = self.client.get(
            "/api/models/test-model/?fltr=title=title_test_model_2&fltr=id=2"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == 2
        assert response.json()[0]["title"] == "title_test_model_2"

        response = self.client.get(
            "/api/models/test-model/?fltr=title=title_test_model_2&fltr=id=3"
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = self.client.get(
            "/api/models/test-model/?fltr=title__in=[title_test_model_2,title_test_model_3]"
        )
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["id"] == 3
        assert response.json()[0]["title"] == "title_test_model_3"
        assert response.json()[1]["id"] == 2
        assert response.json()[1]["title"] == "title_test_model_2"

        response = self.client.get(
            "/api/models/test-model/?fltr=title__in=[title_test_model_4,title_test_model_3]"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == 3
        assert response.json()[0]["title"] == "title_test_model_3"

    @pytest.mark.django_db
    def test_model_api_register_listing_filtered_model(self):
        # Create filter argument register model 1
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "test 1"},
            format="json",
        )
        assert response.status_code == 201

        # Create filter argument register model 2
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "pippo 2"},
            format="json",
        )
        assert response.status_code == 201

        # Create filter argument register model 3
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "3 test"},
            format="json",
        )
        assert response.status_code == 201

        response = self.client.get("/api/models/filtered-register-model/")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["id"] == 3
        assert response.json()[0]["field_filtered"] == "3 test"
        assert response.json()[1]["id"] == 1
        assert response.json()[1]["field_filtered"] == "test 1"

    @pytest.mark.django_db
    def test_model_api_register_base_view_search(self):
        # Verify search_fields = ["description"]
        # Create custom arguments register model 1
        response = self.client.post(
            "/api/models/custom-base-arguments-register-model/",
            {"description": "description_1"},
            format="json",
        )
        assert response.status_code == 201

        # Create custom arguments register model 2
        response = self.client.post(
            "/api/models/custom-base-arguments-register-model/",
            {"description": "description_2"},
            format="json",
        )
        assert response.status_code == 201

        # Create custom arguments register model 3
        response = self.client.post(
            "/api/models/custom-base-arguments-register-model/",
            {"description": "description_3"},
            format="json",
        )
        assert response.status_code == 201

        response = self.client.get(
            "/api/models/custom-base-arguments-register-model/?search=not_real_description"
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = self.client.get(
            "/api/models/custom-base-arguments-register-model/?search=description_1"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == 1
        assert response.json()[0]["description"] == "description_1"

    @pytest.mark.django_db
    def test_model_api_register_base_serializer_search(self):
        # Verify description = BaseModelSerializer.CharField(min_length=3)
        # Create custom arguments register model 1
        response = self.client.post(
            "/api/models/custom-base-arguments-register-model/",
            {"description": "12"},
            format="json",
        )
        assert response.status_code == 400

        # Create custom arguments register model 2
        response = self.client.post(
            "/api/models/custom-base-arguments-register-model/",
            {"description": "1234"},
            format="json",
        )
        assert response.status_code == 201

    @pytest.mark.django_db
    def test_model_api_register_view_search(self):
        # Verify {"search_fields": ["name"]}
        # Create custom arguments register model 1
        response = self.client.post(
            "/api/models/custom-arguments-register-model/",
            {"name": "name_1"},
            format="json",
        )
        assert response.status_code == 201

        # Create custom arguments register model 2
        response = self.client.post(
            "/api/models/custom-arguments-register-model/",
            {"name": "name_2"},
            format="json",
        )
        assert response.status_code == 201

        # Create custom arguments register model 3
        response = self.client.post(
            "/api/models/custom-arguments-register-model/",
            {"name": "name_3"},
            format="json",
        )
        assert response.status_code == 201

        response = self.client.get(
            "/api/models/custom-arguments-register-model/?search=not_real_name"
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = self.client.get(
            "/api/models/custom-arguments-register-model/?search=name_1"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "name_1"

    @pytest.mark.django_db
    def test_model_api_register_serializer_search(self):
        # Verify {"fields": ["name"]}
        # Create custom arguments register model
        response = self.client.post(
            "/api/models/custom-arguments-register-model/",
            {"name": "1234"},
            format="json",
        )
        assert response.status_code == 201
        assert "id" not in response.json()
        assert response.json()["name"] == "1234"

    @pytest.mark.django_db
    def test_model_api_register_listing_filtered_model(self):
        # Verify filters={"field_filtered__icontains": "test"}
        # Create filter argument register model 1
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "test 1"},
            format="json",
        )
        assert response.status_code == 201

        # Create filter argument register model 2
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "pippo 2"},
            format="json",
        )
        assert response.status_code == 201

        # Create filter argument register model 3
        response = self.client.post(
            "/api/models/filtered-register-model/",
            {"field_filtered": "3 test"},
            format="json",
        )
        assert response.status_code == 201

        response = self.client.get("/api/models/filtered-register-model/")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["id"] == 3
        assert response.json()[0]["field_filtered"] == "3 test"
        assert response.json()[1]["id"] == 1
        assert response.json()[1]["field_filtered"] == "test 1"
