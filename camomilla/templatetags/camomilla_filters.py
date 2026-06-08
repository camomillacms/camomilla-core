from django import template
from django.utils.translation import get_language


register = template.Library()


@register.filter(name="filter_content")
def filter_content(page, args):
    try:
        content = page.contents.get(identifier=args)
    except page.contents.model.DoesNotExist:
        content, _ = page.contents.get_or_create(identifier=args)
    return content


@register.filter(name="alternate_urls")
def alternate_urls(page, request):
    alternates = page.alternate_urls(request)
    return alternates.get("alternate_urls", alternates).items()


@register.filter(name="strip_lang")
def strip_lang(value, lang=get_language()):
    return "/%s" % value.lstrip("/%s/" % lang)


@register.simple_tag(name="localized_url", takes_context=True)
def localized_url(context, permalink):
    """Resolve a camomilla permalink to a URL in the current language.

    Use this whenever a template renders a navigation target stored as
    a raw camomilla permalink (typically inside ``template_data``,
    ``Content`` blocks, or any other free-form JSON field). The tag
    looks up the matching ``UrlNode`` and returns its routerlink — which
    honors both Django's ``i18n_patterns`` (adds the active-language
    prefix) and ``APPEND_SLASH`` (canonical trailing slash).

    When a ``request`` is in the template context (the standard
    ``django.template.context_processors.request`` puts it there), the
    returned URL is absolute (scheme + host); otherwise it's
    root-relative.

    Behavior:

    * permalink resolves to a real UrlNode → returns its routerlink
      (e.g. ``"/about"`` rendered while IT is active → ``"/it/about/"``,
      or ``"https://host/it/about/"`` when a request is in context).
    * permalink doesn't resolve (typo, deleted page, external link,
      ``mailto:`` etc.) → returns the input unchanged so the link
      degrades to its raw form instead of erroring.

    Example::

        {% load camomilla_filters %}
        <a href="{% localized_url page.template_data.hero.cta_url %}">CTA</a>
    """
    if not permalink or not isinstance(permalink, str):
        return permalink
    # Anything that doesn't look like an internal absolute path passes
    # through unchanged — external links (``https://...``), in-page
    # anchors (``#...``), ``mailto:``, ``tel:`` etc.
    if not permalink.startswith("/"):
        return permalink
    from camomilla.models.page import UrlNode

    request = context.get("request")
    return UrlNode.reverse_url(permalink, request=request) or permalink
