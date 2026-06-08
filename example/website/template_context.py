from camomilla.templates_context.rendering import register
from camomilla.models import Article, Media, Page


# ---------------------------------------------------------------------------
# Existing test-suite registrations — DO NOT TOUCH. ``tests/test_templates_context.py``
# asserts on the literal keys returned here.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Demo-site context injections — used by the ``seed_demo`` fixtures.
# Each function targets one of the templates we ship under
# ``website/templates/website/pages/``. The registry MERGES the dicts
# returned by every matching registration, so adding entries here is safe.
#
# All page lookups go through ``Page.objects.public()`` /
# ``Article.objects.public()`` — never ``filter(status='PUB')``, which
# was removed in camomilla 6.4 in favor of timestamp-derived lifecycle.
# ---------------------------------------------------------------------------


@register("website/pages/home.html")
def website_home_context():
    """Featured articles strip on the homepage."""
    return {
        "featured_articles": Article.objects.public().order_by("-date_created")[:3],
    }


@register("website/pages/services.html")
def website_services_context(super_ctx):
    """Render the immediate child pages as service cards.

    ``page.childs`` already filters to the right related-set for the page
    model, but it doesn't gate on lifecycle — explicitly chain ``.public()``
    so trashed/draft children stay hidden.
    """
    page = super_ctx.get("page")
    if page is None:
        return {}
    return {"child_pages": page.childs.public()}


@register("website/pages/blog_list.html")
def website_blog_list_context():
    return {
        "blog_articles": Article.objects.public().order_by("-date_created"),
    }


@register("website/articles/detail.html")
def website_article_detail_context(super_ctx):
    """Related articles share at least one tag with the current article."""
    article = super_ctx.get("page")
    if article is None or not isinstance(article, Article):
        return {}
    tag_ids = list(article.tags.values_list("pk", flat=True))
    related = (
        Article.objects.public()
        .filter(tags__in=tag_ids)
        .exclude(pk=article.pk)
        .distinct()[:2]
    )
    return {"related_articles": related}
