import responses
from django.test import TestCase
from camomilla.models import Page
from camomilla.utils.templates import get_templates
from camomilla.theme.admin import PageAdmin
from django.contrib.admin.sites import AdminSite
from camomilla.settings import INTEGRATIONS_ASTRO_URL

class MockRequest:
    def __init__(self):
        self.COOKIES = {
            "sessionid": "mock_session_id",
            "csrftoken": "mock_csrf_token"
        }

request = MockRequest()

class AdminPageFormTestCase(TestCase):
    def setUp(self):
        self.astro_api_url = INTEGRATIONS_ASTRO_URL + "/api/templates"

    @responses.activate
    def test_admin_page_form(self):
        responses.add(
            responses.GET,
            self.astro_api_url,
            json=["mock_template/1", "mock_template/2"],
            status=200,
        )

        page_admin = PageAdmin(Page, AdminSite())
        form = page_admin.get_form(request)()
        self.assertEqual(
            len(list(form.fields)), 33
        )
        self.assertTrue(
            "template" in list(form.fields)
        )
        self.assertListEqual(
            form.fields["template"].widget.choices,
            [('', '---------')] + [(t, t) for t in get_templates(request)]
        )
        self.assertEqual(responses.calls[0].request.url, self.astro_api_url)