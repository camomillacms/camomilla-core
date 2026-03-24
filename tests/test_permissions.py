from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory
from camomilla.permissions import CamomillaBasePermissions, CamomillaSuperUser, ReadOnly
from camomilla.models import Page


class PermissionsTestCase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = CamomillaBasePermissions()
        self.superuser_permission = CamomillaSuperUser()
        self.readonly_permission = ReadOnly()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.superuser = User.objects.create_superuser(username='admin', password='admin')
        self.page = Page.objects.create(title_it='Test Page')

    def test_camomilla_base_permissions_superuser(self):
        # Test superuser has permission
        request = self.factory.get('/')
        request.user = self.superuser
        view = type('View', (), {'model': Page})()
        self.assertTrue(self.permission.has_permission(request, view))
        self.assertTrue(self.permission.has_object_permission(request, view, self.page))

    def test_camomilla_base_permissions_authenticated_user_safe_method(self):
        # Test authenticated user with safe method
        request = self.factory.get('/')
        request.user = self.user
        view = type('View', (), {'model': Page})()
        self.assertTrue(self.permission.has_permission(request, view))

    def test_camomilla_base_permissions_authenticated_user_unsafe_method(self):
        # Test authenticated user with unsafe method - should check permissions
        request = self.factory.post('/')
        request.user = self.user
        view = type('View', (), {'model': Page})()
        # User doesn't have permissions, so should return False
        self.assertFalse(self.permission.has_permission(request, view))

    def test_camomilla_base_permissions_unauthenticated(self):
        # Test unauthenticated user
        request = self.factory.get('/')
        request.user = type('AnonymousUser', (), {'is_authenticated': False})()
        view = type('View', (), {'model': Page})()
        self.assertFalse(self.permission.has_permission(request, view))
        self.assertFalse(self.permission.has_object_permission(request, view, self.page))

    def test_camomilla_superuser_permission(self):
        # Test superuser
        request = self.factory.get('/')
        request.user = self.superuser
        view = type('View', (), {})()
        self.assertTrue(self.superuser_permission.has_permission(request, view))
        self.assertTrue(self.superuser_permission.has_object_permission(request, view, self.page))

        # Test non-superuser
        request.user = self.user
        self.assertFalse(self.superuser_permission.has_permission(request, view))
        self.assertFalse(self.superuser_permission.has_object_permission(request, view, self.page))

    def test_readonly_permission(self):
        view = type('View', (), {})()
        
        # Test GET method
        request = self.factory.get('/')
        self.assertTrue(self.readonly_permission.has_permission(request, view))
        
        # Test POST method
        request = self.factory.post('/')
        self.assertFalse(self.readonly_permission.has_permission(request, view))