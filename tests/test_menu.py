import pytest
import html
from django.test import TestCase
from rest_framework.test import APIClient
from .utils.api import login_superuser
from django.template import Template, Context
from camomilla.models import Menu


class MenuTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        token = login_superuser()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

    def renderTemplate(self, template, context=None):
        return Template("{% load menus %}" + template).render(Context(context))

    @pytest.mark.django_db
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

    @pytest.mark.django_db
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

    @pytest.mark.django_db
    def test_template_get_menu_node_url(self):
        self.renderTemplate('{% render_menu "key_5" %}')

        menu = Menu.objects.first()
        menu.nodes = [
            {"title": "key_5_node_title", "link": {"static": "key_5_url_static"}}
        ]
        menu.save()

        rendered = html.unescape(self.renderTemplate('{% render_menu "key_5" %}'))
        assert {'<a href="key_5_url_static">key_5_node_title</a>' in rendered}

    @pytest.mark.django_db
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

    @pytest.mark.django_db
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

        menu = Menu.objects.first()
        menu.nodes = [
            {
                "title": "key_7_node_title",
                "link": {"page": {"id": 1, "model": "camomilla.page"}},
            }
        ]
        menu.save()

        rendered = html.unescape(self.renderTemplate('{% render_menu "key_7" %}'))
        assert {'href="permalink_page_menu_en_1"' in rendered}
