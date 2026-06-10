"""Drafts: a staged future state for a page row, one per language.

Conceptual sibling of django-reversion's ``Version``. A page's live row is
always the published state; pending edits accumulate in :class:`Draft`
rows until an editor publishes, schedules, or discards them.

A Draft is identified by ``(content_type, object_id, language)`` — at most
one pending draft per page per language. The ``serialized`` field carries
the future payload (shape: the body of a PATCH on the page's detail
endpoint, e.g. ``{"translations": {"<lang>": {"title": "..."}}, "ordering": 7}``).
``scheduled_for`` turns a saved draft into a scheduled publish; null means
"apply on demand" (manual publish).

Why a separate table instead of columns on ``AbstractPage``:

* Avoids redundant state — ``has_draft`` etc. used to live on the page
  row and required per-language sync on every write.
* Avoids dragging draft / scheduling metadata through per-subclass
  schemas (multiplies by language count for translated models).
* Decouples scheduling history from the page row — replacing a draft is
  a row swap, not an in-place mutation that loses prior context.
* Mirrors django-reversion: observe + recover from a side table; don't
  smear staged state across the live model.

The HTTP layer (PageViewSet) and the admin both go through model methods
on :class:`AbstractPage` (``save_draft`` / ``publish`` / ``discard_draft`` /
``schedule`` / ``publish_if_due``). The Draft model is the storage and
queryset surface; the model methods own the lifecycle semantics.
"""

from django.conf import settings as django_settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# Sentinel for monolingual rows: the empty string keeps the UNIQUE
# constraint usable (NULL values would let the same (page, NULL) appear
# twice on most DB backends).
NO_LANGUAGE = ""


class DraftQuerySet(models.QuerySet):
    """Lookup helpers around :class:`Draft`.

    Naming mirrors the verb on the page side: ``for_(page, language)``
    narrows to "drafts I'd act on for this page+language",
    ``pending()`` / ``scheduled()`` split by whether ``scheduled_for`` is
    set, ``due_now()`` is the cron / lazy-materialisation worklist.
    """

    def for_(self, page, language=None) -> "DraftQuerySet":
        ct = ContentType.objects.get_for_model(type(page))
        qs = self.filter(content_type=ct, object_id=page.pk)
        if language is not None:
            qs = qs.filter(language=language or NO_LANGUAGE)
        return qs

    def pending(self) -> "DraftQuerySet":
        return self.filter(scheduled_for__isnull=True)

    def scheduled(self) -> "DraftQuerySet":
        return self.filter(scheduled_for__isnull=False)

    def due_now(self, now=None) -> "DraftQuerySet":
        return self.filter(scheduled_for__lte=now or timezone.now())


class Draft(models.Model):
    """One staged future state of a page in one language."""

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    # ``""`` for monolingual installs; the concrete language code (``"en"``,
    # ``"it"``, …) for translatable models. See :data:`NO_LANGUAGE`.
    language = models.CharField(max_length=10, default=NO_LANGUAGE, blank=True)

    serialized = models.JSONField(default=dict, blank=True)

    scheduled_for = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    objects = DraftQuerySet.as_manager()

    class Meta:
        verbose_name = _("Draft")
        verbose_name_plural = _("Drafts")
        # One pending draft per (page, language). update_or_create on
        # ``save_draft`` enforces the contract; the unique index is the
        # belt-and-braces guarantee at the DB layer.
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "language"],
                name="unique_draft_per_page_language",
            ),
        ]
        indexes = [
            models.Index(fields=["scheduled_for"]),
        ]
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        lang = self.language or "—"
        when = self.scheduled_for.isoformat() if self.scheduled_for else "manual"
        return f"Draft[{lang}] for {self.content_type}/{self.object_id} ({when})"
