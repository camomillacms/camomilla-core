from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from example.website.models import (
    DefaultApiSerializerModel,
    CustomApiSerializerModel
)

client = APIClient()


class StandardApiSerializer(TestCase):
    def setUp(self):
        self.description_value = "Description Field Value"
        token = login_superuser()
        client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def test_default_api_serializer(self):
        DefaultApiSerializerModel.objects.create(
            title="DefaultApiSerializerModel 1",
            permalink="default-api-serializer-model-1",
            status="PUB",
            autopermalink=False,
            description=self.description_value
        )

        response = client.get('/api/camomilla/pages-router/default-api-serializer-model-1')
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == self.description_value
        assert "added_field" not in data

    def test_custom_api_serializer(self):
        CustomApiSerializerModel.objects.create(
            title="CustomApiSerializerModel 1",
            permalink="custom-api-serializer-model-1",
            status="PUB",
            autopermalink=False,
            description=self.description_value
        )

        response = client.get('/api/camomilla/pages-router/custom-api-serializer-model-1')
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == f'{self.description_value}-CustomApiSerializer'
        assert data["added_field"] == "This is an added field from CustomApiSerializerModelSerializer"