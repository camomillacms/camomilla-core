from camomilla.templates_context.rendering import register
from camomilla.models import Media, Page


@register("website/page_context_template_based.html")
def website_page_context_template_based():
    return {
        "page_context_template_based": {
            "title": "Title page for page context template based",
            "content": "Content page for page context template based",
            "media_gallery": Media.objects.all(),
        }
    }


@register("website/page_context_mixed.html")
def website_page_context_template_based():
    return {
        "page_context_template_based": {
            "title": "Title page for page context template based",
            "content": "Content page for page context template based",
            "media_gallery": Media.objects.all(),
        }
    }


@register(page_model=Page)
def website_page_context_model_based():
    return {
        "page_context_model_based": {
            "title": "Title page for page context model based",
            "content": "Content page for page context model based",
            "media_gallery": Media.objects.all(),
        }
    }
