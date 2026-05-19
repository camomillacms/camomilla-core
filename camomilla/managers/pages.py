"""Querysets and managers for ``AbstractPage`` and ``UrlNode``.

The page lifecycle is visibility-only and reads from two timestamps on
the page row:

    published_at : the moment live content goes / went public (per language)
    deleted_at   : the moment the page was soft-deleted (global)

Drafts and scheduled publishes live in :class:`camomilla.models.draft.Draft`;
this module surfaces them via EXISTS subqueries (``.draft()``,
``.scheduled()``, ``.due_for_publish()``) so callers can mix lifecycle
state with draft presence without joining manually.

This module exposes:

* annotation:     ``computed_status`` (PUB / DRF / PLA / TRS)
* filter helpers: ``.public()``, ``.scheduled()``, ``.due_for_publish()``,
                  ``.trashed()``, ``.alive()``, ``.draft()``,
                  ``.first_publish_pending()``
"""

from typing import Sequence, Tuple

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    DateTimeField,
    Exists,
    F,
    OuterRef,
    Q,
    Value,
    When,
)
from django.db.models.query import QuerySet
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from camomilla.utils import localized_fieldname


URL_NODE_RELATED_NAME = "%(app_label)s_%(class)s"

# Lifecycle status labels — kept identical to the constants in models.page
# so callers can match on either side without coupling to that module.
PAGE_STATUS_PUBLISHED = "PUB"
PAGE_STATUS_DRAFT = "DRF"
PAGE_STATUS_SCHEDULED = "PLA"
PAGE_STATUS_TRASHED = "TRS"


def _draft_exists_subquery(model_cls, *, scheduled=None, due_now=False):
    """Build an ``Exists`` subquery against the :class:`Draft` table.

    ``scheduled``:
        * ``None`` — any draft (pending or scheduled).
        * ``True`` — only scheduled drafts (``scheduled_for IS NOT NULL``).
        * ``False`` — only pending drafts.
    ``due_now``: narrows to drafts whose ``scheduled_for`` has passed.

    The subquery filters by ContentType ID and the outer ``pk`` so it
    works across every AbstractPage subclass with a single ``Draft``
    table (generic FK).
    """
    from camomilla.models.draft import Draft

    ct = ContentType.objects.get_for_model(model_cls)
    qs = Draft.objects.filter(content_type=ct, object_id=OuterRef("pk"))
    if scheduled is True:
        qs = qs.filter(scheduled_for__isnull=False)
    elif scheduled is False:
        qs = qs.filter(scheduled_for__isnull=True)
    if due_now:
        qs = qs.filter(scheduled_for__lte=timezone.now())
    return Exists(qs)


def _is_public_q(now=None) -> Q:
    """Q for "live content reachable to the public right now".

    Uses ``localized_fieldname('published_at')`` so modeltranslation can
    auto-rewrite the lookup to the active-language column in filter
    contexts; for annotate contexts callers should pass the resolved
    column name themselves.
    """
    now = now or timezone.now()
    return Q(deleted_at__isnull=True) & Q(
        **{f"{localized_fieldname('published_at')}__lte": now}
    )


class PageQuerySet(QuerySet):
    """Lifecycle-aware queryset for any ``AbstractPage`` subclass.

    Always usable directly (no need to call ``with_lifecycle()`` first) — the
    filter helpers compile their conditions from raw timestamp fields and
    Draft EXISTS subqueries so they work even on an un-annotated queryset.
    """

    __UrlNodeModel = None

    # -- url-node lookup glue (used by .get(permalink=...)) ---------------

    @property
    def UrlNodeModel(self):
        if not self.__UrlNodeModel:
            self.__UrlNodeModel = apps.get_model("camomilla", "UrlNode")
        return self.__UrlNodeModel

    def get_permalink_kwargs(self, kwargs):
        return list(
            set(kwargs.keys()).intersection(
                set(self.UrlNodeModel.LANG_PERMALINK_FIELDS + ["permalink"])
            )
        )

    def get(self, *args, **kwargs):
        permalink_args = self.get_permalink_kwargs(kwargs)
        if len(permalink_args):
            try:
                node = self.UrlNodeModel.objects.get(
                    **{arg: kwargs.pop(arg) for arg in permalink_args}
                )
                kwargs["url_node"] = node
            except ObjectDoesNotExist:
                raise self.model.DoesNotExist(
                    "%s matching query does not exist." % self.model._meta.object_name
                )
        return super().get(*args, **kwargs)

    # -- lifecycle annotations -------------------------------------------

    def with_lifecycle(self):
        """Annotate ``computed_status`` — the SQL-derived lifecycle label
        (PUB / DRF / PLA / TRS) for ``ORDER BY``, ``GROUP BY`` or
        ``.values()`` listings.

        Mirrors :meth:`camomilla.models.page.AbstractPage._lifecycle_label`:
        visibility is a function of ``deleted_at`` and the per-language
        ``published_at``; drafts do NOT contribute to ``status``.

        Per-language: ``Case``/``When`` references inside ``annotate()`` are
        NOT rewritten by ``modeltranslation``, so we resolve the
        per-language column once via ``localized_fieldname(target=...)``
        and wire it explicitly.
        """
        now = timezone.now()
        published_col = localized_fieldname("published_at", target=self.model)
        return self.annotate(
            computed_status=Case(
                When(deleted_at__isnull=False, then=Value(PAGE_STATUS_TRASHED)),
                When(
                    **{f"{published_col}__lte": now},
                    then=Value(PAGE_STATUS_PUBLISHED),
                ),
                # Rule 2 already short-circuited for ``published_at <= now``;
                # any remaining row with ``published_at IS NOT NULL`` is in
                # the future, i.e. a legacy scheduled-first-publish.
                When(
                    **{f"{published_col}__isnull": False},
                    then=Value(PAGE_STATUS_SCHEDULED),
                ),
                default=Value(PAGE_STATUS_DRAFT),
                output_field=CharField(),
            ),
        )

    # -- filter helpers --------------------------------------------------

    def public(self):
        """Pages whose live content is reachable to the public right now."""
        return self.filter(_is_public_q())

    def trashed(self):
        return self.filter(deleted_at__isnull=False)

    def alive(self):
        """Not soft-deleted (may or may not be public)."""
        return self.filter(deleted_at__isnull=True)

    def draft(self):
        """Pages carrying any pending Draft row (any language)."""
        return self.annotate(
            _has_any_draft=_draft_exists_subquery(self.model)
        ).filter(_has_any_draft=True)

    def scheduled(self):
        """Pages with a future publish action queued.

        Two valid sources of "scheduled":

        * A Draft row with ``scheduled_for`` set (content swap).
        * The page's ``published_at`` is in the future (legacy
          "scheduled first publish").

        Returns the union of both.
        """
        now = timezone.now()
        published_col = localized_fieldname(
            "published_at", target=self.model
        )
        return self.annotate(
            _has_scheduled_draft=_draft_exists_subquery(
                self.model, scheduled=True
            )
        ).filter(
            Q(_has_scheduled_draft=True)
            | Q(**{f"{published_col}__gt": now})
        )

    def due_for_publish(self):
        """Pages with a Draft whose ``scheduled_for`` has passed.

        ``Draft.language`` is the canonical per-language marker — the
        cron / lazy-materialisation worklist iterates Drafts directly
        (see :func:`camomilla.preview.resolve_scheduled_pages`); this
        helper is the page-side equivalent for ad-hoc queries.
        """
        return self.annotate(
            _has_due_draft=_draft_exists_subquery(self.model, due_now=True)
        ).filter(_has_due_draft=True)

    def first_publish_pending(self):
        """Never-public pages with a future ``published_at``: the legacy
        "scheduled to first appear at X" bucket. Independent of Draft
        state."""
        now = timezone.now()
        return self.filter(
            deleted_at__isnull=True,
            published_at__isnull=False,
            published_at__gt=now,
        )


class UrlNodeManager(models.Manager):

    def get_reverse_pages_relations(self):
        """
        Get all reverse relations coming from AbstractPages models.
        This is used to annotate the UrlNode with the related page fields.
        """
        from camomilla.models.page import AbstractPage

        relations = []

        for field in self.model._meta.get_fields():
            if not (hasattr(field, "related_model") and field.one_to_one):
                continue

            if not issubclass(field.related_model, AbstractPage):
                continue

            if field.remote_field.name != "url_node":
                continue

            related_name = field.get_accessor_name()
            relations.append(
                {
                    "name": related_name,
                    "model": field.related_model,
                    "field_name": field.remote_field.name,
                    "field": field,
                }
            )
        return relations

    @property
    def related_names(self):
        self._related_names = getattr(self, "_related_names", None)
        if self._related_names is None:
            self._related_names = list(
                set([rel["name"] for rel in self.get_reverse_pages_relations()])
            )
        return self._related_names

    def _annotate_fields(
        self,
        qs: models.QuerySet,
        field_names: Sequence[Tuple[str, models.Field, models.Value]],
    ):
        """Annotate UrlNode rows with fields pulled from the related page.

        Each F-join target is resolved to the **active-language** column on
        the related model (via ``localized_fieldname(target=model)``).
        ``modeltranslation`` rewrites lookups on the page side automatically
        but F expressions through a foreign-key join are NOT rewritten —
        without this we'd read the base column (whose value bears no
        per-language meaning when translations are enabled) and the
        downstream ``is_public`` annotation would lie across languages.
        """
        relations_by_name = {
            rel["name"]: rel["model"] for rel in self.get_reverse_pages_relations()
        }
        for field_name, output_field, default in field_names:
            whens = [
                When(
                    related_name=related_name,
                    then=F(
                        "__".join(
                            [
                                related_name,
                                localized_fieldname(
                                    field_name,
                                    target=relations_by_name[related_name],
                                ),
                            ]
                        )
                    ),
                )
                for related_name in self.related_names
            ]
            qs = qs.annotate(
                **{field_name: Case(*whens, output_field=output_field, default=default)}
            )
        return self._annotate_lifecycle(qs)

    def _annotate_lifecycle(self, qs: models.QuerySet):
        """Annotate ``is_public`` + ``status`` on UrlNodes.

        Both are derived from the page's ``published_at`` / ``deleted_at``
        timestamps (already surfaced onto the UrlNode by
        ``_annotate_fields`` via per-concrete-model joins). ``status``
        no longer consults ``publish_at`` — that column doesn't exist
        anymore; scheduled content swaps live in the ``Draft`` table
        and don't affect the UrlNode's visibility label.
        """
        now = timezone.now()
        return qs.annotate(
            is_public=Case(
                When(
                    deleted_at__isnull=True,
                    published_at__lte=now,
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
            status=Case(
                When(deleted_at__isnull=False, then=Value(PAGE_STATUS_TRASHED)),
                When(published_at__lte=now, then=Value(PAGE_STATUS_PUBLISHED)),
                When(
                    published_at__isnull=False,
                    then=Value(PAGE_STATUS_SCHEDULED),
                ),
                default=Value(PAGE_STATUS_DRAFT),
                output_field=CharField(),
            ),
        )

    def get_queryset(self):
        try:
            return self._annotate_fields(
                super().get_queryset(),
                [
                    (
                        "indexable",
                        BooleanField(),
                        Value(None, BooleanField()),
                    ),
                    (
                        "published_at",
                        DateTimeField(),
                        Value(None, DateTimeField()),
                    ),
                    (
                        "deleted_at",
                        DateTimeField(),
                        Value(None, DateTimeField()),
                    ),
                    (
                        "date_updated_at",
                        DateTimeField(),
                        Value(timezone.now(), DateTimeField()),
                    ),
                ],
            )
        except (ProgrammingError, OperationalError):
            return super().get_queryset()
