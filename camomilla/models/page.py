import logging
from typing import Sequence, Tuple, Optional
from uuid import uuid4

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
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


logger = logging.getLogger(__name__)


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
            for lang in settings.LANGUAGE_CODES
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
                url = reverse("camomilla-homepage")
            else:
                url = reverse("camomilla-permalink", args=(permalink.lstrip("/"),))
                if append_slash and not url.endswith("/"):
                    url += "/"
            # Both branches funnel through here so an absolute URI is built
            # for the homepage too — not only for sub-paths.
            if request:
                url = request.build_absolute_uri(url)
            return url
        except NoReverseMatch:
            return None

    @property
    def routerlink(self) -> str:
        return self.reverse_url(self.permalink) or self.permalink

    def get_routerlink(self, request: Optional[HttpRequest] = None) -> str:
        """Request-aware ``routerlink``. Same value as the property, but
        absolute (scheme + host) when a request is supplied. Use this from
        any code path that has a request in hand (template tags, serializer
        ``to_representation`` with ``context['request']``); fall back to the
        bare :attr:`routerlink` property when you don't."""
        return self.reverse_url(self.permalink, request=request) or self.permalink

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

# Lifecycle labels — computed at read time from the visibility pair
# (published_at, deleted_at). Drafts (scheduled or not) don't affect the
# label; they're surfaced via the separate ``has_draft`` /
# ``has_scheduled_draft`` properties. Kept as constants so callers and
# templates that want a human-readable lifecycle string have a stable name.
PAGE_STATUS_PUBLISHED = "PUB"
PAGE_STATUS_DRAFT = "DRF"
PAGE_STATUS_SCHEDULED = "PLA"
PAGE_STATUS_TRASHED = "TRS"

PAGE_STATUS_CHOICES = (
    (PAGE_STATUS_PUBLISHED, _("Published")),
    (PAGE_STATUS_DRAFT, _("Draft")),
    (PAGE_STATUS_TRASHED, _("Trash")),
    (PAGE_STATUS_SCHEDULED, _("Planned")),
)

# Kept under the old name for any external code that imported it.
PAGE_STATUS = PAGE_STATUS_CHOICES


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
    # Visibility — derived lifecycle (PUB / PLA / DRF / TRS) reads from
    # these two timestamps alone. Drafts and scheduled publishes live on
    # the ``camomilla.Draft`` table (see :mod:`camomilla.models.draft`).
    published_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    indexable = models.BooleanField(default=True)
    autopermalink = models.BooleanField(default=True)
    contents = GenericRelation(
        "camomilla.Content",
        content_type_field="content_type",
        object_id_field="object_id",
        related_query_name="page",
    )

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
            "permalink": self.routerlink,
            "title": self.breadcrumbs_title or self.title or "",
        }
        if self.parent:
            return self.parent.breadcrumbs + [breadcrumb]
        return [breadcrumb]

    # ------------------------------------------------------------------
    # Lifecycle status — visibility-only derivation
    # ------------------------------------------------------------------
    #
    # ``status`` / ``is_public`` are functions of two things and two things
    # only: ``deleted_at`` (global, "is the row hidden?") and the per-
    # language ``published_at`` ("when did this language go live?"). Drafts
    # do NOT affect status — they're a separate concept observable via the
    # ``Draft`` table (``has_draft`` / ``has_scheduled_draft`` properties).

    def _lifecycle_label(self) -> str:
        """In-memory Python computation of the lifecycle label.

        Mirrors the SQL ``Case`` expression in
        :meth:`camomilla.managers.pages.PageQuerySet.with_lifecycle`. The
        invariant is enforced by ``test_lifecycle_property_matches_db_layer``.
        """
        if get_nofallbacks(self, "deleted_at") is not None:
            return PAGE_STATUS_TRASHED
        now = timezone.now()
        published_at = get_nofallbacks(self, "published_at")
        if published_at is not None and published_at <= now:
            return PAGE_STATUS_PUBLISHED
        if published_at is not None:
            # Future stamp — legacy "scheduled first publish".
            return PAGE_STATUS_SCHEDULED
        return PAGE_STATUS_DRAFT

    @property
    def status(self) -> str:
        return self._lifecycle_label()

    @property
    def is_public(self) -> bool:
        return self._lifecycle_label() == PAGE_STATUS_PUBLISHED

    # ------------------------------------------------------------------
    # Draft accessors — per-active-language helpers around the Draft table
    # ------------------------------------------------------------------

    @staticmethod
    def _draft_language() -> str:
        """Active language code to use for draft lookups.

        For monolingual installs we use the empty string (``NO_LANGUAGE``)
        so the same ``UNIQUE(content_type, object_id, language)`` constraint
        works without NULL-vs-NULL backend quirks. Translated installs use
        the active Django language.
        """
        from camomilla.models.draft import NO_LANGUAGE
        from django.utils.translation import get_language

        return get_language() or NO_LANGUAGE

    def _drafts(self, language=None):
        """Queryset of Drafts for this page (filtered by language if given)."""
        from camomilla.models.draft import Draft

        return Draft.objects.for_(self, language=language)

    @property
    def has_draft(self) -> bool:
        """True when a pending draft exists for the active language."""
        return self._drafts(language=self._draft_language()).exists()

    @property
    def has_scheduled_draft(self) -> bool:
        return self._drafts(language=self._draft_language()).scheduled().exists()

    @property
    def overlay_due(self) -> bool:
        """The active language's draft is due (scheduled_for ≤ now)."""
        return self._drafts(language=self._draft_language()).due_now().exists()

    @property
    def draft_data(self) -> dict:
        """The active language's pending draft payload (or ``{}``).

        Kept as a property — not a column — so callers that just want to
        inspect the staged state still have an ergonomic accessor. Compare
        :meth:`save_draft` for writes.
        """
        draft = self._drafts(language=self._draft_language()).first()
        return dict(draft.serialized) if draft else {}

    # ------------------------------------------------------------------
    # Draft write surface — every mutation goes through the Draft model
    # ------------------------------------------------------------------

    def save_draft(self, data: dict, merge: bool = True, *, scheduled_for=None) -> None:
        """Persist ``data`` as the pending draft for the active language.

        ``merge=True`` (default) merges into the existing draft body so a
        partial PATCH only updates the named keys; ``merge=False`` replaces
        wholesale. ``scheduled_for`` lets callers stage and schedule in one
        call; pass ``None`` to keep the existing schedule (or no schedule).
        """
        from camomilla.models.draft import Draft

        lang = self._draft_language()
        ct = ContentType.objects.get_for_model(type(self))
        draft, created = Draft.objects.get_or_create(
            content_type=ct,
            object_id=self.pk,
            language=lang,
            defaults={
                "serialized": dict(data),
                "scheduled_for": scheduled_for,
            },
        )
        if not created:
            current = dict(draft.serialized or {})
            draft.serialized = {**current, **data} if merge else dict(data)
            if scheduled_for is not None:
                draft.scheduled_for = scheduled_for
            draft.save(
                update_fields=["serialized", "scheduled_for", "updated_at"]
                if scheduled_for is not None
                else ["serialized", "updated_at"]
            )

    def discard_draft(self) -> None:
        self._drafts(language=self._draft_language()).delete()

    def _apply_draft_via_serializer(self, draft_data: dict) -> None:
        """Apply ``draft_data`` through the model's edit serializer.

        Validates the payload as if it had arrived through the API's PATCH
        path. Keeps nested ``translations`` round-tripping correctly via the
        write-shaped base chain (``get_editable_bases``).
        """
        if not draft_data:
            return
        from camomilla.serializers.utils import (
            build_standard_model_serializer,
            get_editable_bases,
        )

        serializer_cls = build_standard_model_serializer(
            self.__class__,
            bases=get_editable_bases(self.__class__.get_serializer()),
            name_suffix="Draft",
        )
        instance = self.__class__.objects.get(pk=self.pk)
        serializer = serializer_cls(instance, data=draft_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.refresh_from_db()

    def publish(self, *, create_revision: bool = True, comment: str = "") -> None:
        """Apply the active-language draft (if any) and mark the row public.

        - Loads the active language's Draft, applies its ``serialized``
          payload through the publish serializer, then deletes the Draft.
        - Stamps ``published_at = now()`` (only if unset or in the future,
          to keep repeated ``publish()`` idempotent against an already-live
          page).
        - Snapshots a reversion revision for revert.
        """
        from camomilla.preview import reversion_available

        draft = self._drafts(language=self._draft_language()).first()
        had_draft = draft is not None
        if had_draft:
            self._apply_draft_via_serializer(draft.serialized)
            draft.delete()

        now = timezone.now()
        current_published_at = get_nofallbacks(self, "published_at")
        if current_published_at is None or current_published_at > now:
            self.published_at = now

        if create_revision and reversion_available():
            import reversion

            with reversion.create_revision():
                self.save()
                reversion.set_comment(
                    comment
                    or ("Published with pending draft" if had_draft else "Published")
                )
        else:
            self.save()

    def publish_if_due(self) -> bool:
        """Lazy-publish the active language's due Draft, if there is one.

        Concurrency: the locked SELECT is on the Draft row, not the page.
        Two concurrent reads contend for the Draft; the loser observes the
        row has been consumed and returns ``False``.

        Expected runtime failures (validation, transient DB) are caught
        and logged; the request proceeds with whatever lives in the DB
        now. Programmer errors propagate.
        """
        from django.db.utils import DatabaseError, NotSupportedError, OperationalError
        from rest_framework.exceptions import ValidationError

        from camomilla.models.draft import Draft

        lang = self._draft_language()
        if not Draft.objects.for_(self, language=lang).due_now().exists():
            return False
        try:
            with transaction.atomic():
                try:
                    locked = (
                        Draft.objects.select_for_update()
                        .for_(self, language=lang)
                        .due_now()
                        .first()
                    )
                except (NotSupportedError, OperationalError):
                    locked = (
                        Draft.objects.for_(self, language=lang).due_now().first()
                    )
                if locked is None:
                    return False
                # Re-fetch page under the lock to read fresh published_at.
                page = self.__class__.objects.get(pk=self.pk)
                page._apply_draft_via_serializer(locked.serialized)
                now = timezone.now()
                current = get_nofallbacks(page, "published_at")
                if current is None or current > now:
                    page.published_at = now
                from camomilla.preview import reversion_available

                if reversion_available():
                    import reversion

                    with reversion.create_revision():
                        page.save()
                        reversion.set_comment("Auto-published on first read")
                else:
                    page.save()
                locked.delete()
        except (ValidationError, DatabaseError) as exc:
            logger.warning(
                "publish_if_due skipped for %s pk=%s: %s",
                type(self).__name__,
                self.pk,
                exc,
            )
            self.refresh_from_db()
            return False
        self.refresh_from_db()
        return True

    def schedule(self, when, *, create_revision: bool = False) -> None:
        """Schedule the next publish moment for the active language.

        Two paths, depending on whether the active language has ever been
        public:

        * **Never public** (``published_at IS NULL``) — set ``published_at
          = when`` so the page enters the "scheduled first publish" bucket.
          No Draft is required: the live row IS the content that will
          appear at ``when``.
        * **Already public** — attach ``scheduled_for=when`` to the
          existing Draft (must be saved first via :meth:`save_draft`). The
          public live content stays visible until ``when``; the Draft's
          payload swaps in at that moment.

        Calling :meth:`schedule` against an already-public page with no
        Draft is a no-op + warning — there's nothing to schedule.
        """
        from camomilla.preview import reversion_available

        lang = self._draft_language()
        current_published_at = get_nofallbacks(self, "published_at")
        if current_published_at is None:
            # First-appearance schedule: the live row becomes the future
            # content.
            self.published_at = when
            if create_revision and reversion_available():
                import reversion

                with reversion.create_revision():
                    self.save()
                    reversion.set_comment(f"Scheduled for {when.isoformat()}")
            else:
                self.save()
            return

        # Already public: schedule the existing draft.
        draft = self._drafts(language=lang).first()
        if draft is None:
            logger.warning(
                "schedule() called on a live %s pk=%s with no pending draft "
                "in language %r — nothing to schedule.",
                type(self).__name__,
                self.pk,
                lang,
            )
            return
        draft.scheduled_for = when
        draft.save(update_fields=["scheduled_for", "updated_at"])

    def trash(self) -> None:
        """Soft-delete the page. Reversible via :meth:`restore`."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "date_updated_at"])

    def restore(self) -> None:
        """Undo :meth:`trash` (the page returns to whatever lifecycle state
        its timestamps describe)."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "date_updated_at"])

    def list_revisions(self):
        """Return the ``reversion`` versions for this page (newest first)."""
        from camomilla.preview import reversion_available

        if not reversion_available():
            return []
        from reversion.models import Version

        return Version.objects.get_for_object(self)

    def revert_to_revision(self, version_id: int) -> None:
        """Revert the page state to the given reversion ``Version``.

        Restores both the page fields and the associated ``UrlNode`` state
        captured at revision time (so manually-set permalinks round-trip).
        """
        from camomilla.preview import reversion_available

        if not reversion_available():
            raise RuntimeError("django-reversion is not installed")
        import reversion
        from reversion.models import Version

        version = Version.objects.get_for_object(self).get(pk=version_id)
        with reversion.create_revision():
            version.revision.revert(delete=False)
            reversion.set_comment(f"Reverted to revision {version_id}")
        self.refresh_from_db()

    def get_template_path(self, request: Optional[HttpRequest] = None) -> str:
        return self.template or pointed_getter(self, "_page_meta.default_template")

    @property
    def childs(self) -> models.Manager:
        if hasattr(self._page_meta, "child_page_field"):
            return getattr(self, self._page_meta.child_page_field)
        return getattr(
            self,
            PAGE_CHILD_RELATED_NAME % self.model_info,
            self.__class__.objects.none(),
        )

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
                message = "Match found: %s.\nThe page appears not to be public." % page
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
        """Return the page at ``/``, creating it on the fly if missing.

        Auto-created homepages are stamped as **publicly published right
        now** (per language). The public ``fetch()`` route bypasses the
        ``is_public`` check on this branch and renders whatever it gets,
        but other lifecycle surfaces — ``Page.objects.public()``, the
        sitemap, the admin status column, ``page.is_public`` — would
        otherwise see the row as DRAFT. Stamping ``published_at`` on
        creation keeps every surface in agreement instead of having one
        path silently serve a row that the rest of the system thinks is
        unpublished.

        ``published_at`` is translatable, so we cycle through every
        language and set the per-language column. Monolingual models get
        the base column written (``localized_fieldname`` falls back).
        """
        try:
            if settings.ENABLE_TRANSLATIONS:
                node = UrlNode.objects.get(lang_fallback_query(permalink="/"))
            else:
                node = UrlNode.objects.get(permalink="/")
            return node.page, False
        except UrlNode.DoesNotExist:
            page, created = cls.get_or_create(None, permalink="/")
            if created and page is not None:
                now = timezone.now()
                for lang in activate_languages():
                    set_nofallbacks(page, "published_at", now, language=lang)
                page.save()
            return page, created

    @classmethod
    def get_or_404(cls, request: HttpRequest, *args, **kwargs) -> "AbstractPage":
        try:
            return cls.get(request, *args, **kwargs)
        except ObjectDoesNotExist as ex:
            raise Http404(ex)

    def alternate_urls(self, *args, **kwargs) -> dict:
        permalinks = get_field_translations(self.url_node or object, "permalink", None)
        for lang in activate_languages():
            if lang in permalinks and permalinks[lang]:
                permalinks[lang] = (
                    UrlNode.reverse_url(permalinks[lang]) if self.is_public else None
                )
        permalinks.pop(get_language(), None)
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
