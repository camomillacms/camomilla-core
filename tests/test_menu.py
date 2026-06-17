import pytest
import html
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TransactionTestCase, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.template import Template, Context, RequestContext
from rest_framework.test import APIClient
from .utils.api import login_superuser
from camomilla.models import Menu
from camomilla.models.menu import LinkTypes, MenuNodeLink
from camomilla.models.page import Page, UrlNode
from camomilla.serializers.page import UrlNodeSerializer


class MenuTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def renderTemplate(self, template, context=None):
        return Template("{% load menus %}" + template).render(Context(context))

    def test_template_render_menu(self):
        assert self.renderTemplate('{% render_menu "key_1" %}') == "\n\n"
        assert len(Menu.objects.all()) == 1
        menu = Menu.objects.first()
        assert menu.id == 1
        assert menu.key == "key_1"

        assert self.renderTemplate('{% render_menu "key_2" %}') == "\n\n"
        assert len(Menu.objects.all()) == 2
        menu = Menu.objects.last()
        assert menu.id == 2
        assert menu.key == "key_2"

    def test_template_get_menus(self):
        self.renderTemplate('{% render_menu "key_3" %}')
        self.renderTemplate('{% render_menu "key_4" %}')

        rendered = html.unescape(self.renderTemplate("{% get_menus %}"))
        assert rendered == "{'key_3': <Menu: key_3>, 'key_4': <Menu: key_4>}"

        rendered = html.unescape(self.renderTemplate('{% get_menus "arg" %}'))
        assert rendered == "{}"

        rendered = html.unescape(self.renderTemplate('{% get_menus "key_3" %}'))
        assert rendered == "{'key_3': <Menu: key_3>}"

        menus = 'test "menus" in context'
        rendered = html.unescape(
            self.renderTemplate("{% get_menus %}", {"menus": menus})
        )
        assert rendered == menus

    def test_template_get_menu_node_url(self):
        self.renderTemplate('{% render_menu "key_5" %}')

        menu = Menu.objects.first()
        menu.nodes = [
            {"title": "key_5_node_title", "link": {"static": "key_5_url_static"}}
        ]
        menu.save()

        rendered = html.unescape(self.renderTemplate('{% render_menu "key_5" %}'))
        assert {'<a href="key_5_url_static">key_5_node_title</a>' in rendered}

    def test_menu_custom_template(self):
        self.renderTemplate('{% render_menu "key_6_custom" %}')

        menu = Menu.objects.first()
        menu.nodes = [
            {"title": "key_6_node_title", "link": {"static": "key_6_url_static"}}
        ]
        menu.save()

        rendered = html.unescape(
            self.renderTemplate(
                '{% render_menu "key_6_custom" "website/menu_custom.html" %}'
            )
        )
        assert {"This is custom menu: key_6_node_title" in rendered}

    def test_menu_in_page_template(self):
        self.renderTemplate('{% render_menu "key_7" %}')

        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "en": {
                        "title": "title_page_menu_1",
                        "permalink": "permalink_page_menu_en_1",
                        "autopermalink": False,
                    }
                }
            },
            format="json",
        )
        assert response.status_code == 201
        page = Page.objects.get(pk=response.json()["id"])

        menu = Menu.objects.first()
        menu.nodes = [
            {
                "title": "key_7_node_title",
                "link": {
                    "link_type": LinkTypes.relational.value,
                    "url_node": page.url_node_id,
                },
            }
        ]
        menu.save()

        rendered = html.unescape(self.renderTemplate('{% render_menu "key_7" %}'))
        assert "<a " in rendered
        assert "permalink_page_menu_en_1" in rendered

    def test_menu_node_link_relational_derives_page(self):
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "en": {
                        "title": "relational_page",
                        "permalink": "relational_permalink_en",
                        "autopermalink": False,
                    }
                }
            },
            format="json",
        )
        assert response.status_code == 201
        page = Page.objects.get(pk=response.json()["id"])
        url_node = page.url_node
        assert isinstance(url_node, UrlNode)

        link = MenuNodeLink(link_type=LinkTypes.relational, url_node=url_node.pk)
        assert link.page is not None
        assert link.page.pk == page.pk
        assert link.content_type is not None
        assert link.content_type.model_class() is Page

        link_with_instance = MenuNodeLink(
            link_type=LinkTypes.relational, url_node=url_node
        )
        assert link_with_instance.get_url() == url_node.routerlink
        assert link_with_instance.url == url_node.routerlink

    def test_menu_node_link_relational_metadata_is_lazy(self):
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "en": {
                        "title": "lazy_relational_page",
                        "permalink": "lazy_relational_permalink_en",
                        "autopermalink": False,
                    }
                }
            },
            format="json",
        )
        assert response.status_code == 201
        page = Page.objects.get(pk=response.json()["id"])
        url_node = page.url_node

        ContentType.objects.clear_cache()
        payload = {
            "link_type": LinkTypes.relational.value,
            "url_node": url_node.pk,
            # Old stored payloads may still carry these derived fields. They
            # must be ignored; relational links are keyed only by url_node.
            "page": {"id": page.pk, "model": "camomilla.page"},
            "content_type": {"id": 9999},
        }
        with CaptureQueriesContext(connection) as captured:
            link = MenuNodeLink.model_validate(payload)
            assert link.url == url_node.routerlink

        sql = "\n".join(q["sql"] for q in captured.captured_queries)
        assert 'FROM "camomilla_page"' not in sql
        assert 'FROM "django_content_type"' not in sql

        dumped = link.model_dump()
        assert "page" not in dumped
        assert "content_type" not in dumped
        assert dumped["url"] == url_node.routerlink

        assert link.page.pk == page.pk
        assert link.content_type.model_class() is Page

    def test_url_node_with_page_selects_page_relation(self):
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "en": {
                        "title": "with_page_relation",
                        "permalink": "with_page_relation",
                        "autopermalink": False,
                    }
                }
            },
            format="json",
        )
        assert response.status_code == 201
        page = Page.objects.get(pk=response.json()["id"])
        node = UrlNode.objects.with_page().get(pk=page.url_node_id)

        with CaptureQueriesContext(connection) as captured:
            assert node.page.pk == page.pk

        assert len(captured) == 0

    def test_url_node_serializer_uses_annotations_without_page_query(self):
        response = self.client.post(
            "/api/camomilla/pages/",
            {
                "translations": {
                    "en": {
                        "title": "serializer_annotations",
                        "permalink": "serializer_annotations",
                        "autopermalink": False,
                    }
                }
            },
            format="json",
        )
        assert response.status_code == 201
        page = Page.objects.get(pk=response.json()["id"])
        # with_lifecycle() annotates is_public/status/indexable; the serializer
        # reads those scalars and never dereferences .page.
        node = UrlNode.objects.with_lifecycle().get(pk=page.url_node_id)

        with CaptureQueriesContext(connection) as captured:
            data = UrlNodeSerializer(node).data

        sql = "\n".join(q["sql"] for q in captured.captured_queries)
        assert 'FROM "camomilla_page"' not in sql
        assert data["indexable"] == page.indexable
        assert data["is_public"] == page.is_public
        assert data["status"] == page.status

    def test_menu_node_link_static_get_url(self):
        link = MenuNodeLink(link_type=LinkTypes.static, static="/about")
        assert link.get_url() == "/about"
        assert link.url == "/about"

    def test_menu_render_with_request_context(self):
        menu, _ = Menu.objects.get_or_create(key="render_ctx_menu")
        menu.nodes = [{"title": "ctx_node", "link": {"static": "/ctx-url"}}]
        menu.save()

        request = RequestFactory().get("/?preview=true")
        ctx = RequestContext(request, {"extra": "value"})
        rendered = menu.render("defaults/parts/menu.html", request=request, context=ctx)
        assert "ctx_node" in rendered
        assert "/ctx-url" in rendered

    def test_menu_api_actions(self):
        # Test page_types action
        response = self.client.get("/api/camomilla/menus/page_types/")
        assert response.status_code == 200
        page_types = response.json()
        assert isinstance(page_types, list)
        # Should include Page and Article at least
        assert len(page_types) >= 2

        # Test page_type_instances action - need a content type id
        if page_types:
            content_type_id = page_types[0]["id"]
            response = self.client.get(
                f"/api/camomilla/menus/page_types/{content_type_id}/"
            )
            assert response.status_code == 200
            instances = response.json()
            assert isinstance(instances, list)

        # Test search_urlnode action
        response = self.client.get("/api/camomilla/menus/search_urlnode/?q=test")
        assert response.status_code == 200
        results = response.json()
        assert isinstance(results, list)

        # Test accessing menu by key
        content = self.renderTemplate('{% render_menu "api_test_menu" %}')
        assert content != ""
        response = self.client.get("/api/camomilla/menus/api_test_menu/")
        assert response.status_code == 200
        menu_data = response.json()
        assert menu_data["key"] == "api_test_menu"
