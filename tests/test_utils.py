import os
import mock

from camomilla.utils import get_host_url, get_complete_url, get_page
from camomilla.exceptions import NeedARedirect
from camomilla.models import Page, Article

from django.http import Http404
from django.test import TestCase
from django.test import RequestFactory
from django.utils.translation import activate, get_language

from requests import RequestException


# class UtilsTestCase(TestCase):
#     def setUp(self):
#         pass

#     def test_get_host_url(self):
#         """Our beloved get_host_url utility"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/path")
#         request.META["HTTP_HOST"] = "localhost"
#         host_url = get_host_url(request)
#         self.assertEqual(host_url, "http://localhost")
#         host_url = get_host_url(None)
#         self.assertEqual(host_url, None)

#     def test_get_complete_url(self):
#         """Our beloved get_complete_url utility"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/path")
#         request.META["HTTP_HOST"] = "localhost"
#         complete_url = get_complete_url(request, "path")
#         self.assertEqual(complete_url, "http://localhost/path")
#         complete_url = get_complete_url(request, "path", "it")
#         self.assertEqual(complete_url, "http://localhost/path")
#         complete_url = get_complete_url(request, "path", "fr")
#         self.assertEqual(complete_url, "http://localhost/fr/path")

#     def test_get_page_with_default_seo(self):
#         """Our beloved get_seo utility with auto attributes"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/path")
#         request.META["HTTP_HOST"] = "localhost"
#         page = Page.get(request, identifier="home")
#         self.assertEqual(page.og_url, "http://localhost/path")
#         self.assertEqual(page.canonical, "http://localhost/path")

#     def test_get_article_with_default_seo(self):
#         """Our beloved get_seo utility with auto attributes"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/path")
#         request.META["HTTP_HOST"] = "localhost"
#         Article.objects.create(permalink="main")
#         article = Article.get(request, permalink="main")
#         self.assertEqual(article.og_url, "http://localhost/path")
#         self.assertEqual(article.canonical, "http://localhost/path")

#     def test_compile_seo_overwrite(self):
#         """Our beloved get_seo utility with auto attributes"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/path")
#         request.META["HTTP_HOST"] = "localhost"
#         article = Article.objects.create(permalink="main")
#         article.canonical = "/myarticle"
#         article.og_url = "/myarticle"
#         article.save()
#         article = Article.get(request, permalink="main")
#         self.assertEqual(article.og_url, "http://localhost/myarticle")
#         self.assertEqual(article.canonical, "http://localhost/myarticle")

#     def test_get_article_with_redirect(self):
#         """Our beloved get_seo utility with auto attributes"""
#         request_factory = RequestFactory()
#         request = request_factory.get("/articles/articolo-1")
#         request.META["HTTP_HOST"] = "localhost"

#         article = Article.objects.create(permalink="article-1", language_code="en")
#         article.translate("it")
#         article.permalink = "articolo-1"
#         article.save()
#         self.assertRaises(NeedARedirect, Article.get, request, permalink="article-1")
#         activate("de")
#         self.assertRaises(Http404, Article.get, request, permalink="article-1")
