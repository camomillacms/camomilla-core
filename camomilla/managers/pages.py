"""Querysets and managers for ``AbstractPage`` and ``UrlNode``.

The page lifecycle is driven entirely by three timestamps on the page row:

    published_at : the moment live content goes / went public
    publish_at   : the moment the pending draft should next be applied
    deleted_at   : the moment the page was soft-deleted

This module exposes those facts at the queryset level via:

* annotations:    ``is_public``, ``is_scheduled``, ``has_overlay_due``,
                  ``computed_status``
* filter helpers: ``.public()``, ``.scheduled()``, ``.due_for_publish()``,
                  ``.trashed()``, ``.alive()``, ``.draft()``,
                  ``.first_publish_pending()``

The legacy ``status`` field has been removed from the model; the
``computed_status`` annotation (and the matching property on the model)
gives back a PUB/DRF/PLA/TRS string for callers that still want a label.
"""

from typing import Sequence, Tuple

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    DateTimeField,
    F,
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


def _is_public_q(now=None) -> Q:
    """Q expression for "live content is reachable to the public right now".

    ``published_col`` lets callers point at a specific language column
    (e.g. ``published_at_en``); defaults to the base name, which
    ``modeltranslation`` rewrites to the active-language column inside
    ``filter()`` / ``exclude()``. The override is used for ``annotate()``
    contexts where modeltranslation doesn't rewrite.
    """
    now = now or timezone.now()
    return Q(deleted_at__isnull=True) & Q(**{f"{localized_fieldname('published_at')}__lte": now})


def _overlay_due_q(now=None) -> Q:
    """Q expression for "a pending draft is due to be applied"."""
    now = now or timezone.now()
    return Q(has_draft=True) & Q(**{f"{localized_fieldname('publish_at')}__lte": now})


def _scheduled_q(now=None) -> Q:
    """Q expression for "a future publish is queued"."""
    now = now or timezone.now()
    return Q(**{f"{localized_fieldname('publish_at')}__isnull": False}) & Q(**{f"{localized_fieldname('publish_at')}__gt": now})


class PageQuerySet(QuerySet):
    """Lifecycle-aware queryset for any ``AbstractPage`` subclass.

    Always usable directly (no need to call ``with_lifecycle()`` first) — the
    filter helpers compile their conditions from raw timestamp fields so they
    work even on an un-annotated queryset.
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

        Boolean derivations (``is_public``, ``has_overlay_due``,
        ``is_scheduled``) are NOT annotated here on purpose: they collide
        with the equivalent ``@property`` declarations on ``AbstractPage``
        (Django setattr's annotations onto the instance, but properties
        without setters error). Use the filter helpers
        (``.public()`` / ``.due_for_publish()`` / ``.scheduled()``) for
        DB-level filtering, and the properties for instance reads. The
        ``computed_status`` annotation here is the single SQL output that
        adds value beyond what the helpers/properties already provide.

        Per-language: ``Case``/``When`` references inside ``annotate()`` are
        NOT rewritten by ``modeltranslation``, so we resolve the
        per-language column once via ``localized_fieldname(target=...)``
        and wire it explicitly.
        """
        now = timezone.now()
        published_col = localized_fieldname("published_at", target=self.model)
        publish_col = localized_fieldname("publish_at", target=self.model)
        return self.annotate(
            computed_status=Case(
                When(deleted_at__isnull=False, then=Value(PAGE_STATUS_TRASHED)),
                When(
                    **{f"{published_col}__lte": now},
                    then=Value(PAGE_STATUS_PUBLISHED),
                ),
                # Rule 2 already covered ``published_at <= now``, so reaching
                # this branch with ``published_at IS NOT NULL`` implies a
                # future stamp — equivalent to the Python ``_lifecycle_label``
                # which drops the ``> now`` comparison for the same reason.
                When(
                    Q(**{f"{publish_col}__isnull": False})
                    | Q(**{f"{published_col}__isnull": False}),
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
        """Pages carrying a non-empty draft overlay."""
        return self.filter(has_draft=True)

    def scheduled(self):
        """Pages with a future publish action queued."""
        return self.filter(_scheduled_q())

    def due_for_publish(self):
        """Pages whose ``publish_at`` (in the **active language**) has
        passed and still have a draft.

        ``publish_at`` is translatable, so this filter only matches against
        the language currently active. Use
        :func:`camomilla.preview.resolve_scheduled_pages` if you need to
        scan every language (the cron's worklist).
        """
        return self.filter(_overlay_due_q())

    def first_publish_pending(self):
        """Never-public pages with a future ``published_at``: the legacy
        "scheduled to first appear at X" bucket."""
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
        # related_name → related model, so each F-join can be resolved to the
        # right per-language column for that specific related model.
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
        """Annotate ``is_public`` + the legacy ``status`` label on UrlNodes.

        Both are derived from the page's ``published_at`` / ``publish_at`` /
        ``deleted_at`` timestamps (already surfaced onto the UrlNode by
        ``_annotate_fields`` via per-concrete-model joins).
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
                    Q(publish_at__isnull=False) | Q(published_at__gt=now),
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
                        "publish_at",
                        DateTimeField(),
                        Value(None, DateTimeField()),
                    ),
                    (
                        "deleted_at",
                        DateTimeField(),
                        Value(None, DateTimeField()),
                    ),
                    (
                        "has_draft",
                        BooleanField(),
                        Value(False, BooleanField()),
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
