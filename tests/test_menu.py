import pytest
import html
from django.test import TestCase
from django.template import Template, Context
from camomilla.models import Menu


class MenuTestCase(TestCase):
    def setUp(self):
        pass

    def renderTemplate(self, template, context = None):
        return Template('{% load menus %}' + template).render(Context(context))

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

        rendered = html.unescape(self.renderTemplate('{% get_menus %}'))
        assert rendered == "{'key_3': <Menu: key_3>, 'key_4': <Menu: key_4>}"

        rendered = html.unescape(self.renderTemplate('{% get_menus "arg" %}'))
        assert rendered == "{}"

        rendered = html.unescape(self.renderTemplate('{% get_menus "key_3" %}'))
        assert rendered == "{'key_3': <Menu: key_3>}"
        
        menus = 'test "menus" in context'
        rendered =  html.unescape(self.renderTemplate('{% get_menus %}', {"menus": menus}))
        assert rendered == menus

    @pytest.mark.django_db
    def test_template_get_menu_node_url(self):
        self.renderTemplate('{% render_menu "key_5" %}')

        menu = Menu.objects.first()
        menu.nodes = [{"title": "key_5_node_title", "link":{"static": "key_5_url_static"}}]
        menu.save()

        rendered = html.unescape(self.renderTemplate('{% render_menu "key_5" %}'))
        assert {'<a href="key_5_url_static">key_5_node_title</a>' in rendered}
