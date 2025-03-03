from django import template
from camomilla.models import Menu

from camomilla.models.menu import MenuNode

register = template.Library()


@register.simple_tag(takes_context=True)
def get_menus(context, *args):
    if "menus" in context:
        return context["menus"]
    qs = Menu.objects.all()
    if len(args):
        qs = qs.filter(key__in=args)
    return Menu.defaultdict({m.key: m for m in qs})


@register.simple_tag(takes_context=True)
def render_menu(
    context: template.RequestContext,
    menu_key: str,
    template_path: str = "defaults/parts/menu.html",
):
    if context is not None and not isinstance(context, dict):
        context = context.__dict__

    return context.get("menus", Menu.defaultdict())[menu_key].render(
        template_path=template_path,
        context=context,
        request=context.get("request", None),
    )


@register.filter(name="node_url")
def get_menu_node_url(node: MenuNode):
    return node.link.url
