from camomilla.utils import get_host_url, get_complete_url, get_templates

from django.test import TestCase
from django.test import RequestFactory
import responses
from camomilla.settings import INTEGRATIONS_ASTRO_API_URL


class UtilsTestCase(TestCase):
    def setUp(self):
        pass

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
            INTEGRATIONS_ASTRO_API_URL,
            json=["Error"],
            status=400,
        )
        templates = get_templates(request=RequestFactory().get("/"))
        self.assertFalse("Astro: Error" in templates)
        self.assertEqual(responses.calls[0].request.url, INTEGRATIONS_ASTRO_API_URL)

    @responses.activate
    def test_get_all_templates_files(self):
        responses.add(
            responses.GET,
            INTEGRATIONS_ASTRO_API_URL,
            json=["mock_template/1", "mock_template/2"],
            status=200,
        )
        templates = get_templates(request=RequestFactory().get("/"))
        self.assertTrue("astro/mock_template/1" in templates)
        self.assertTrue("astro/mock_template/2" in templates)
        self.assertEqual(responses.calls[0].request.url, INTEGRATIONS_ASTRO_API_URL)