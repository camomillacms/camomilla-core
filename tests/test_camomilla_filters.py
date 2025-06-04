import os
import mock

from django.http import Http404
from django.test import TestCase
from django.test import RequestFactory
from django.utils.translation import activate, get_language

from camomilla.models import Page, Article
from camomilla.templatetags.camomilla_filters import filter_content, alternate_urls

from requests import RequestException


class CamomillaFiltersTestCase(TestCase):
    def setUp(self):
        pass

    def test_filter_content(self):
        Page.objects.create(
            identifier="path", title="Path", permalink="/path", status="PUB"
        )
        request_factory = RequestFactory()
        request = request_factory.get("/path")
        request.META["HTTP_HOST"] = "localhost"
        page = Page.get(request)
        content = filter_content(page, "content1")
        self.assertEqual(content.identifier, "content1")
        self.assertEqual(content.content, "")
        content.content = "Hello World!"
        content.save()
        page = Page.get(request)
        content = filter_content(page, "content1")
        self.assertEqual(content.identifier, "content1")
        self.assertEqual(content.content, "Hello World!")

    def test_filter_alternate_urls(self):
        Page.objects.create(
            identifier="path", title="Path", permalink="/path", status="PUB"
        )
        request = RequestFactory().get("/path")
        request.META["HTTP_HOST"] = "localhost"
        page = Page.get(request)
        alt_urls = dict(alternate_urls(page, request))
        self.assertEqual(alt_urls, {"it": None, "en": "/path/"})
