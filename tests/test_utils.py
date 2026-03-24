from camomilla.utils import (
    get_host_url, 
    get_complete_url, 
    get_templates,
    is_page,
    get_page,
    get_seo_model,
    compile_seo,
    find_or_redirect
)

from django.test import TestCase
from django.test import RequestFactory
import responses
from camomilla.settings import INTEGRATIONS_ASTRO_URL
from camomilla.models import Page


class UtilsTestCase(TestCase):
    def setUp(self):
        self.astro_api_url = INTEGRATIONS_ASTRO_URL + "/api/templates"

    def test_get_host_url(self):
        request_factory = RequestFactory()
        request = request_factory.get("/path")
        request.META["HTTP_HOST"] = "localhost"
        host_url = get_host_url(request)
        self.assertEqual(host_url, "http://localhost")
        host_url = get_host_url(None)
        self.assertEqual(host_url, None)

    def test_get_complete_url(self):
        request_factory = RequestFactory()
        request = request_factory.get("/path")
        request.META["HTTP_HOST"] = "localhost"
        complete_url = get_complete_url(request, "path")
        self.assertEqual(complete_url, "http://localhost/path")
        complete_url = get_complete_url(request, "path", "it")
        self.assertEqual(complete_url, "http://localhost/it/path")
        complete_url = get_complete_url(request, "path", "fr")
        self.assertEqual(complete_url, "http://localhost/fr/path")

    @responses.activate
    def test_get_all_templates_files_error(self):
        responses.add(
            responses.GET,
            self.astro_api_url,
            json=["Error"],
            status=400,
        )
        templates = get_templates(request=RequestFactory().get("/"))
        self.assertFalse("Astro: Error" in templates)
        self.assertEqual(responses.calls[0].request.url, self.astro_api_url)

    @responses.activate
    def test_get_all_templates_files(self):
        responses.add(
            responses.GET,
            self.astro_api_url,
            json=["mock_template/1", "mock_template/2"],
            status=200,
        )
        templates = get_templates(request=RequestFactory().get("/"))
        self.assertTrue("mock_template/1" in templates)
        self.assertTrue("mock_template/2" in templates)
        self.assertEqual(responses.calls[0].request.url, self.astro_api_url)

    def test_is_page(self):
        # Test with Page model
        self.assertTrue(is_page(Page))
        # Test with non-page model
        from django.contrib.auth.models import User
        self.assertFalse(is_page(User))

    def test_get_page(self):
        request_factory = RequestFactory()
        request = request_factory.get("/test-page")
        request.META["HTTP_HOST"] = "localhost"
        
        # Create a test page
        page = Page.objects.create(title_it="Test Page", identifier="test-page")
        
        # Test get_page
        result_page = get_page(request, identifier="test-page")
        self.assertEqual(result_page.id, page.id)
        self.assertEqual(result_page.title, "Test Page")  # Should be compiled

    def test_compile_seo(self):
        request_factory = RequestFactory()
        request = request_factory.get("/test-page")
        request.META["HTTP_HOST"] = "localhost"
        
        # Create a page with some SEO fields
        page = Page.objects.create(
            title_it="Test Page",
            og_title_it="OG Title",
            canonical="custom-canonical",  # Without leading /
            og_url="custom-og-url"  # Without leading /
        )
        
        # Test compile_seo
        compiled_page = compile_seo(request, page, "it")
        self.assertEqual(compiled_page.og_title, "OG Title")
        self.assertEqual(compiled_page.canonical, "http://localhost/it/custom-canonical")
        self.assertEqual(compiled_page.og_url, "http://localhost/it/custom-og-url")

    def test_get_seo_model(self):
        request_factory = RequestFactory()
        request = request_factory.get("/test-page")
        request.META["HTTP_HOST"] = "localhost"
        
        # Create a page
        page = Page.objects.create(title_it="Test Page", identifier="test-page")
        
        # Test get_seo_model
        seo_page = get_seo_model(request, Page, identifier="test-page")
        self.assertEqual(seo_page.id, page.id)
        self.assertIsNotNone(seo_page.canonical)

    def test_find_or_redirect(self):
        # Test finding existing object
        page = Page.objects.create(title_it="Test Page", identifier="test-page")
        found_page = find_or_redirect(None, Page, identifier="test-page")
        self.assertEqual(found_page.id, page.id)
        
        # Test with non-existing object - should raise Http404
        from django.http import Http404
        with self.assertRaises(Http404):
            find_or_redirect(None, Page, identifier="non-existing")
