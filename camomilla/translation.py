from modeltranslation.translator import TranslationOptions, register

from camomilla.models import Article, Content, Media, Page, Tag, UrlNode, Menu


class SeoMixinTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "description",
        "og_description",
        "og_title",
        "og_type",
        "og_url",
        "canonical",
    )


class AbstractPageTranslationOptions(SeoMixinTranslationOptions):
    fields = (
        "breadcrumbs_title",
        "autopermalink",
        "status",
        "indexable",
        "template_data",
    )


@register(Article)
class ArticleTranslationOptions(AbstractPageTranslationOptions):
    fields = ("content",)


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Content)
class ContentTranslationOptions(TranslationOptions):
    fields = ("content",)
    empty_values = {"title": None}


@register(Media)
class MediaTranslationOptions(TranslationOptions):
    fields = ("title", "alt_text", "description")


@register(Page)
class PageTranslationOptions(AbstractPageTranslationOptions):
    pass


@register(UrlNode)
class UrlNodeTranslationOptions(TranslationOptions):
    fields = ("permalink",)


@register(Menu)
class MenuTranslationOptions(TranslationOptions):
    fields = ("nodes",)
