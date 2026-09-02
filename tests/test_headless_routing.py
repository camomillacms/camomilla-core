"""URL building must survive a headless install.

Astro/JAMStack projects mount only ``camomilla.urls`` (the API). The HTML
render route lives in ``camomilla.dynamic_pages_urls`` and is deliberately
left out — the frontend owns the routing — so ``reverse()`` has nothing to
resolve. ``reverse_url`` used to return ``None`` there, which made
``alternate_urls`` emit a null per language (dead hreflang links, a language
switcher with every entry disabled) and ``routerlink`` fall back to the bare
permalink, dropping the language prefix.
"""

from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils.translation import activate

from camomilla.models.page import UrlNode

# No ``dynamic_pages_urls``: this is the headless shape.
urlpatterns = [path("api/camomilla/", include("camomilla.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class HeadlessRoutingTestCase(TestCase):
    def tearDown(self):
        activate("en")

    def test_reverse_url_falls_back_to_the_public_path(self):
        activate("en")  # LANGUAGE_CODE — served unprefixed
        self.assertEqual(UrlNode.reverse_url("/"), "/")
        self.assertEqual(UrlNode.reverse_url("/about"), "/about/")

        activate("it")
        self.assertEqual(UrlNode.reverse_url("/"), "/it/")
        self.assertEqual(UrlNode.reverse_url("/about"), "/it/about/")
