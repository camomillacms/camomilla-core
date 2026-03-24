from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from django.contrib.auth.models import User


class OpenAPISchemaTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create a superuser for authentication
        self.superuser, created = User.objects.get_or_create(
            username='openapi_admin',
            defaults={
                'email': 'openapi_admin@test.com',
                'is_superuser': True,
                'is_staff': True
            }
        )
        if created:
            self.superuser.set_password('admin')
            self.superuser.save()
        self.client.force_authenticate(user=self.superuser)

    def test_openapi_schema_generation(self):
        # Test that the openapi schema endpoint works and exercises the schema generation
        response = self.client.get('/api/camomilla/openapi')
        self.assertEqual(response.status_code, 200)
        # The response is in OpenAPI format (YAML), so we can't parse it as JSON
        # Just check that we get a response with content
        self.assertGreater(len(response.content), 0)
        self.assertIn(b'openapi', response.content)

    def test_openapi_schema_generation_json(self):
        # Test that the openapi schema endpoint works with JSON format
        response = self.client.get('/api/camomilla/openapi?format=openapi-json')
        self.assertEqual(response.status_code, 200)
        # The response should be JSON
        data = response.json()
        self.assertIn('openapi', data)
        self.assertIn('info', data)
        self.assertIn('paths', data)
        # Check that we have some paths defined
        self.assertGreater(len(data['paths']), 0)