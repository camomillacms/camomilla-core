from django.conf import settings as dj_settings
from django.db import models

from camomilla.models.page import AbstractPage
from camomilla import settings


class AbstractArticle(AbstractPage):
    content = models.TextField(default="")
    author = models.ForeignKey(
        dj_settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name="%(app_label)s_%(class)s_authored_articles"
    )
    highlight_image = models.ForeignKey(
        "camomilla.Media",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_highlight_images",
    )
    tags = models.ManyToManyField("Tag", blank=True, related_name="%(app_label)s_%(class)s_tags")

    class Meta:
        abstract = True
        ordering = ["ordering"]


class Article(AbstractArticle):
    class PageMeta:
        default_template = settings.ARTICLE_DEFAULT_TEMPLATE
        inject_context_func = settings.ARTICLE_INJECT_CONTEXT_FUNC


class AbstractTag(models.Model):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        abstract = True

    def __str__(self):
        return "(%s) %s" % (self.__class__.__name__, self.name)


class Tag(AbstractTag):
    pass
