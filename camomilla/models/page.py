from typing import Sequence, Tuple, Optional, Union
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist

from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.http import Http404, HttpRequest
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language

from camomilla.managers.pages import PageQuerySet, UrlNodeManager
from camomilla.models.mixins import MetaMixin, SeoMixin
from camomilla.utils import (
    activate_languages,
    get_field_translations,
    get_nofallbacks,
    lang_fallback_query,
    set_nofallbacks,
    url_lang_decompose,
)
from camomilla.utils.getters import pointed_getter
from camomilla import settings
from camomilla.templates_context.rendering import ctx_registry
from django.conf import settings as django_settings
from modeltranslation.utils import build_localized_fieldname
from django.utils.module_loading import import_string


class UrlRedirect(models.Model):
    language_code = models.CharField(max_length=10, null=True)
    from_url = models.CharField(max_length=400)
    to_url = models.CharField(max_length=400)
    url_node = models.ForeignKey(
        "UrlNode", on_delete=models.CASCADE, related_name="redirects"
    )
    permanent = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated_at = models.DateTimeField(auto_now=True)

    __q_string = ""

    def __str__(self) -> str:
        return f"[{self.language_code}] {self.from_url} -> {self.to_url}"

    @classmethod
    def find_redirect(
        cls, request: HttpRequest, language_code: Optional[str] = None
    ) -> Optional["UrlRedirect"]:
        instance = cls.find_redirect_from_url(request.path, language_code)
        if instance:
            instance.__q_string = request.META.get("QUERY_STRING", "")
        return instance

    @classmethod
    def find_redirect_from_url(
        cls, from_url: str, language_code: Optional[str] = None
    ) -> Optional["UrlRedirect"]:
        path_decomposition = url_lang_decompose(from_url)
        language_code = (
            language_code or path_decomposition["language"] or get_language()
        )
        from_url = path_decomposition["permalink"]
        return cls.objects.filter(
            from_url=from_url.rstrip("/"), language_code=language_code or get_language()
        ).first()

    def redirect(self) -> str:
        return redirect(self.redirect_to, permanent=self.permanent)

    @property
    def redirect_to(self) -> str:
        url_to = "/" + self.to_url.lstrip("/")
        if getattr(django_settings, "APPEND_SLASH", True) and not url_to.endswith("/"):
            url_to += "/"
        if (
            self.language_code != settings.DEFAULT_LANGUAGE
            and settings.ENABLE_TRANSLATIONS
        ):
            url_to = "/" + self.language_code + url_to
        return url_to + ("?" + self.__q_string if self.__q_string else "")

    class Meta:
        verbose_name = _("Redirect")
        verbose_name_plural = _("Redirects")
        unique_together = ("from_url", "language_code")
        indexes = [
            models.Index(fields=["from_url", "language_code"]),
        ]


class UrlNode(models.Model):

    LANG_PERMALINK_FIELDS = (
        [
            build_localized_fieldname("permalink", lang)
            for lang in settings.AVAILABLE_LANGUAGES
        ]
        if settings.ENABLE_TRANSLATIONS
        else ["permalink"]
    )

    permalink = models.CharField(max_length=400, unique=True, null=True)
    related_name = models.CharField(max_length=200)
    objects = UrlNodeManager()

    @property
    def page(self) -> "AbstractPage":
        return getattr(self, self.related_name)

    @staticmethod
    def reverse_url(permalink: str, request: Optional[HttpRequest] = None) -> str:
        append_slash = getattr(django_settings, "APPEND_SLASH", True)
        try:
            if permalink == "/":
                return reverse("camomilla-homepage")
            url = reverse("camomilla-permalink", args=(permalink.lstrip("/"),))
            if append_slash and not url.endswith("/"):
                url += "/"
            if request:
                url = request.build_absolute_uri(url)
            return url
        except NoReverseMatch:
            return None

    @property
    def routerlink(self) -> str:
        return self.reverse_url(self.permalink) or self.permalink

    def get_absolute_url(self) -> str:
        if self.routerlink == "/":
            return ""
        return self.routerlink

    @staticmethod
    def sanitize_permalink(permalink):
        if isinstance(permalink, str):
            p_parts = permalink.split("/")
            permalink = "/".join(
                [slugify(p, allow_unicode=True).strip() for p in p_parts]
            )
            if not permalink.startswith("/"):
                permalink = f"/{permalink}"
        return permalink

    def save(self, *args, **kwargs) -> None:
        for lang_p_field in UrlNode.LANG_PERMALINK_FIELDS:
            setattr(
                self,
                lang_p_field,
                UrlNode.sanitize_permalink(getattr(self, lang_p_field)),
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.permalink


PAGE_CHILD_RELATED_NAME = "%(app_label)s_%(class)s_child_pages"
URL_NODE_RELATED_NAME = "%(app_label)s_%(class)s"

PAGE_STATUS = (
    ("PUB", _("Published")),
    ("DRF", _("Draft")),
    ("TRS", _("Trash")),
    ("PLA", _("Planned")),
)


class PageBase(models.base.ModelBase):
    """
    This models comes to implement a language based permalink logic
    """

    def perm_prop_factory(permalink_field):
        def getter(_self):
            return getattr(
                _self,
                f"__{permalink_field}",
                getattr(_self.url_node or object(), permalink_field, None),
            )

        def setter(_self, value: str):
            setattr(_self, f"__{permalink_field}", value)

        return getter, setter

    def __new__(cls, name, bases, attrs, **kwargs):
        attr_meta = attrs.pop("PageMeta", None)
        new_class = super().__new__(cls, name, bases, attrs, **kwargs)
        page_meta = attr_meta or getattr(new_class, "PageMeta", None)
        base_page_meta = getattr(new_class, "_page_meta", None)
        for lang_p_field in UrlNode.LANG_PERMALINK_FIELDS:
            computed_prop = property(*cls.perm_prop_factory(lang_p_field))
            setattr(new_class, lang_p_field, computed_prop)
        if settings.ENABLE_TRANSLATIONS:
            setattr(
                new_class,
                "permalink",
                property(
                    lambda _self: getattr(
                        _self,
                        build_localized_fieldname("permalink", get_language()),
                        None,
                    ),
                    lambda _self, value: setattr(
                        _self,
                        f"__{build_localized_fieldname('permalink', get_language())}",
                        value,
                    ),
                ),
            )
        if page_meta:
            for name, value in getattr(base_page_meta, "__dict__", {}).items():
                if name not in page_meta.__dict__:
                    setattr(page_meta, name, value)
            setattr(new_class, "_page_meta", page_meta)
        return new_class


class AbstractPage(SeoMixin, MetaMixin, models.Model, metaclass=PageBase):
    identifier = models.CharField(max_length=200, null=True, unique=True, default=uuid4)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated_at = models.DateTimeField(auto_now=True)
    breadcrumbs_title = models.CharField(max_length=128, null=True, blank=True)
    template = models.CharField(max_length=500, null=True, blank=True)
    template_data = models.JSONField(default=dict, null=False, blank=True)
    ordering = models.PositiveIntegerField(default=0, blank=False, null=False)
    parent_page = models.ForeignKey(
        "self",
        related_name=PAGE_CHILD_RELATED_NAME,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    url_node = models.OneToOneField(
        UrlNode,
        on_delete=models.CASCADE,
        related_name=URL_NODE_RELATED_NAME,
        null=True,
        editable=False,
    )
    publication_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=3,
        choices=PAGE_STATUS,
        default="DRF",
    )
    indexable = models.BooleanField(default=True)
    autopermalink = models.BooleanField(default=True)

    objects = PageQuerySet.as_manager()

    __cached_db_instance: "AbstractPage" = None

    @property
    def db_instance(self):
        if self.__cached_db_instance is None:
            self.__cached_db_instance = self.get_db_instance()
        return self.__cached_db_instance

    def get_db_instance(self):
        if self.pk:
            return self.__class__.objects.get(pk=self.pk)
        return None

    def __init__(self, *args, **kwargs):
        super(AbstractPage, self).__init__(*args, **kwargs)

    def __str__(self) -> str:
        return "(%s) %s" % (self.__class__.__name__, self.title or self.permalink)

    def get_context(self, request: Optional[HttpRequest] = None):
        context = {
            "page": self,
            "page_model": {"class": self.__class__.__name__, "module": self.__module__},
            "request": request,
        }
        inject_func = pointed_getter(self, "_page_meta.inject_context_func")
        if inject_func and callable(inject_func):
            new_ctx = inject_func(request=request, super_ctx=context)
            if isinstance(new_ctx, dict):
                context.update(new_ctx)
        return ctx_registry.get_context_for_page(self, request, super_ctx=context)

    @classmethod
    def get_serializer(cls):
        from camomilla.serializers.mixins import AbstractPageMixin

        standard_serializer = (
            pointed_getter(cls, "_page_meta.standard_serializer")
            or settings.PAGES_DEFAULT_SERIALIZER
        )
        if isinstance(standard_serializer, str):
            standard_serializer = import_string(standard_serializer)
        if not issubclass(standard_serializer, AbstractPageMixin):
            raise ValueError(
                f"Standard serializer {standard_serializer} must be a subclass of AbstractPageMixin"
            )
        return standard_serializer

    @property
    def model_name(self) -> str:
        return self._meta.app_label + "." + self._meta.model_name

    @property
    def model_info(self) -> dict:
        return {"app_label": self._meta.app_label, "class": self._meta.model_name}

    @property
    def routerlink(self) -> str:
        return self.url_node and self.url_node.routerlink

    @property
    def breadcrumbs(self) -> Sequence[dict]:
        breadcrumb = {
            "permalink": self.permalink,
            "title": self.breadcrumbs_title or self.title or "",
        }
        if self.parent:
            return self.parent.breadcrumbs + [breadcrumb]
        return [breadcrumb]

    @property
    def is_public(self) -> bool:
        status = get_nofallbacks(self, "status")
        publication_date = get_nofallbacks(self, "publication_date")
        if status == "PUB":
            return True
        if status == "PLA":
            return bool(publication_date) and timezone.now() > publication_date
        return False

    def get_template_path(self, request: Optional[HttpRequest] = None) -> str:
        return self.template or pointed_getter(self, "_page_meta.default_template")

    @property
    def childs(self) -> models.Manager:
        if hasattr(self._page_meta, "child_page_field"):
            return getattr(self, self._page_meta.child_page_field)
        return getattr(self, PAGE_CHILD_RELATED_NAME % self.model_info)

    @property
    def parent(self) -> models.Model:
        return getattr(self, self._page_meta.parent_page_field)

    def _get_or_create_url_node(self) -> UrlNode:
        if not self.url_node:
            self.url_node = UrlNode.objects.create(
                related_name=URL_NODE_RELATED_NAME % self.model_info
            )
        return self.url_node

    def _update_url_node(self, force: bool = False) -> UrlNode:
        self.url_node = self._get_or_create_url_node()
        for __ in activate_languages():
            old_permalink = self.db_instance and self.db_instance.permalink
            new_permalink = self.permalink
            if self.autopermalink:
                new_permalink = self.generate_permalink()
            force = force or old_permalink != new_permalink
            set_nofallbacks(self.url_node, "permalink", new_permalink)
        if force:
            self.url_node.save()
            self.update_childs()
        return self.url_node

    def generate_permalink(self, safe: bool = True) -> str:
        permalink = f"/{slugify(self.title or '', allow_unicode=True)}"
        if self.parent:
            parent_permalink = (self.parent.permalink or "").lstrip("/")
            permalink = f"/{parent_permalink}{permalink}"
        set_nofallbacks(self, "permalink", permalink)
        qs = UrlNode.objects.exclude(pk=getattr(self.url_node or object, "pk", None))
        if safe and qs.filter(permalink=permalink).exists():
            permalink = "/".join(
                permalink.split("/")[:-1] + [slugify(uuid4(), allow_unicode=True)]
            )
        return permalink

    def update_childs(self) -> None:
        # without pk, no childs there
        if self.pk is not None:
            exclude_kwargs = {}
            if self.childs.model == self.__class__:
                exclude_kwargs["pk"] = self.pk
            for child in self.childs.exclude(**exclude_kwargs):
                child.save()

    def save(self, *args, **kwargs) -> None:
        with transaction.atomic():
            self._update_url_node()
            super().save(*args, **kwargs)
            self.__cached_db_instance = None
            for lang_p_field in UrlNode.LANG_PERMALINK_FIELDS:
                hasattr(self, f"__{lang_p_field}") and delattr(
                    self, f"__{lang_p_field}"
                )

    @classmethod
    def get(cls, request: HttpRequest, *args, **kwargs) -> "AbstractPage":
        bypass_type_check = kwargs.pop("bypass_type_check", False)
        bypass_public_check = kwargs.pop("bypass_public_check", False)
        if len(kwargs.keys()) > 0:
            page = cls.objects.get(**kwargs)
        else:
            if not request:
                raise ValueError("request is required if no kwargs are passed")
            path = request.path
            if getattr(django_settings, "APPEND_SLASH", True):
                path = path.rstrip("/")
            node = UrlNode.objects.filter(
                permalink=url_lang_decompose(path)["permalink"]
            ).first()
            page = node and node.page
        type_error = not bypass_type_check and not isinstance(page, cls)
        public_error = not bypass_public_check and not getattr(
            page or object, "is_public", False
        )
        if not page or type_error or public_error:
            bases = (UrlNode.DoesNotExist,)
            if hasattr(cls, "DoesNotExist"):
                bases += (cls.DoesNotExist,)
            message = "%s matching query does not exist." % cls._meta.object_name
            if public_error:
                message = (
                    "Match found: %s.\nThe page appears not to be public.\nUse ?preview=true in the url to see it."
                    % page
                )
            raise type("PageDoesNotExist", bases, {})(message)
        return page

    @classmethod
    def get_or_create(
        cls, request: HttpRequest, *args, **kwargs
    ) -> Tuple["AbstractPage", bool]:
        try:
            return cls.get(request, *args, **kwargs), False
        except ObjectDoesNotExist:
            if len(kwargs.keys()) > 0:
                return cls.objects.get_or_create(**kwargs)
        return (None, False)

    @classmethod
    def get_or_create_homepage(cls) -> Tuple["AbstractPage", bool]:
        try:
            if settings.ENABLE_TRANSLATIONS:
                node = UrlNode.objects.get(lang_fallback_query(permalink="/"))
            else:
                node = UrlNode.objects.get(permalink="/")
            return node.page, False
        except UrlNode.DoesNotExist:
            return cls.get_or_create(None, permalink="/")

    @classmethod
    def get_or_404(cls, request: HttpRequest, *args, **kwargs) -> "AbstractPage":
        try:
            return cls.get(request, *args, **kwargs)
        except ObjectDoesNotExist as ex:
            raise Http404(ex)

    def alternate_urls(self, *args, **kwargs) -> dict:
        request: Union[HttpRequest, bool] = False
        if len(args) > 0:
            request = args[0]
        if "request" in kwargs:
            request = kwargs["request"]
        preview = request and getattr(request, "GET", {}).get("preview", False)
        permalinks = get_field_translations(self.url_node or object, "permalink", None)
        for lang in activate_languages():
            if lang in permalinks and permalinks[lang]:
                permalinks[lang] = (
                    UrlNode.reverse_url(permalinks[lang])
                    if preview or self.is_public
                    else None
                )
            if preview:
                permalinks = {k: f"{v}?preview=true" for k, v in permalinks.items()}
        return permalinks

    class Meta:
        abstract = True
        ordering = ("ordering",)
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    class PageMeta:
        parent_page_field = "parent_page"
        default_template = settings.PAGE_DEFAULT_TEMPLATE
        inject_context_func = settings.PAGE_INJECT_CONTEXT_FUNC
        standard_serializer = settings.PAGES_DEFAULT_SERIALIZER


class Page(AbstractPage):
    pass


@receiver(post_delete)
def auto_delete_url_node(sender, instance, **kwargs):
    if issubclass(sender, AbstractPage):
        instance.url_node and instance.url_node.delete()


__url_node_history__ = {}


@receiver(pre_save, sender=UrlNode)
def cache_url_node(sender, instance, **kwargs):
    if instance.pk:
        __url_node_history__[instance.pk] = sender.objects.filter(
            pk=instance.pk
        ).first()


@receiver(post_save, sender=UrlNode)
def generate_redirects(sender, instance, **kwargs):
    previous = __url_node_history__.pop(instance.pk, None)
    if previous:
        redirects = []
        with transaction.atomic():
            for lang in activate_languages():
                new_permalink = get_nofallbacks(instance, "permalink")
                old_permalink = get_nofallbacks(previous, "permalink")
                UrlRedirect.objects.filter(
                    from_url=new_permalink, language_code=lang
                ).delete()
                if old_permalink and old_permalink != new_permalink:
                    redirects.append(
                        UrlRedirect(
                            from_url=old_permalink,
                            to_url=new_permalink,
                            url_node=instance,
                            language_code=lang,
                        )
                    )
                    UrlRedirect.objects.filter(
                        to_url=old_permalink, language_code=lang
                    ).update(to_url=new_permalink)
            if len(redirects) > 0:
                UrlRedirect.objects.bulk_create(redirects)
