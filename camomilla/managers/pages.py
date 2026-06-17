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


# The four derived lifecycle labels, kept in sync with
# ``AbstractPage._lifecycle_label`` / ``with_lifecycle``.
_LIFECYCLE_STATUSES = frozenset(
    {
        PAGE_STATUS_PUBLISHED,
        PAGE_STATUS_DRAFT,
        PAGE_STATUS_SCHEDULED,
        PAGE_STATUS_TRASHED,
    }
)


def _status_q(label: str, now=None) -> Q:
    """Q selecting pages whose *derived* lifecycle label equals ``label``.

    Query-side mirror of
    :meth:`camomilla.models.page.AbstractPage._lifecycle_label`: there is no
    ``status`` column, so ``.filter(status="PUB")`` is rewritten (by
    :meth:`PageQuerySet._filter_or_exclude`) into the timestamp conditions
    below. The four labels partition the row space exactly the way the
    property does — ``deleted_at`` wins first (``TRS``), then the active
    language's ``published_at``: ``<= now`` → ``PUB``, ``> now`` → ``PLA``,
    ``NULL`` → ``DRF``.
    """
    if label not in _LIFECYCLE_STATUSES:
        raise ValueError(
            f"Unknown lifecycle status {label!r}; expected one of "
            f"{sorted(_LIFECYCLE_STATUSES)}."
        )
    now = now or timezone.now()
    if label == PAGE_STATUS_TRASHED:
        return Q(deleted_at__isnull=False)
    published_col = localized_fieldname("published_at")
    alive = Q(deleted_at__isnull=True)
    if label == PAGE_STATUS_PUBLISHED:
        return alive & Q(**{f"{published_col}__lte": now})
    if label == PAGE_STATUS_SCHEDULED:
        return alive & Q(**{f"{published_col}__gt": now})
    # PAGE_STATUS_DRAFT
    return alive & Q(**{f"{published_col}__isnull": True})


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

    # -- derived-status filtering ----------------------------------------

    def _lifecycle_filter_keys(self):
        """Which of ``status`` / ``is_public`` we may translate.

        Only translate a key when the concrete model does NOT define a real
        field by that name. ``AbstractPage`` exposes ``status`` / ``is_public``
        as read-only *properties* (no column), so they're translated; a
        downstream subclass that adds an actual ``status`` field keeps Django's
        native field filtering instead of being hijacked.
        """
        field_names = {f.name for f in self.model._meta.get_fields()}
        keys = set()
        if "status" not in field_names:
            keys |= {"status", "status__in"}
        if "is_public" not in field_names:
            keys |= {"is_public"}
        return keys

    def _translate_lifecycle_kwargs(self, kwargs):
        """Pop derived ``status`` / ``is_public`` lookups from ``kwargs`` and
        return the equivalent ``Q`` (ANDed), or ``None`` if there's nothing to
        translate. Lets ``.filter()`` / ``.exclude()`` / ``.get()`` accept the
        derived label even though no such column exists.
        """
        translatable = self._lifecycle_filter_keys()
        if not (set(kwargs) & translatable):
            return None
        now = timezone.now()
        combined = Q()
        if "status" in translatable and "status" in kwargs:
            combined &= _status_q(kwargs.pop("status"), now)
        if "status__in" in translatable and "status__in" in kwargs:
            labels = list(kwargs.pop("status__in"))
            if not labels:
                combined &= Q(pk__in=[])  # empty __in matches nothing
            else:
                sub = Q()
                for label in labels:
                    sub |= _status_q(label, now)
                combined &= sub
        if "is_public" in translatable and "is_public" in kwargs:
            public_q = _is_public_q(now)
            combined &= public_q if kwargs.pop("is_public") else ~public_q
        return combined

    def _filter_or_exclude(self, negate, args, kwargs):
        # Rewrite derived-status kwargs into timestamp conditions before
        # Django tries (and fails) to resolve them as real columns. Works for
        # filter(), exclude() and get() (which funnels through here), under the
        # same negate semantics. NOTE: only keyword lookups are translated —
        # ``status`` wrapped inside a ``Q()`` positional arg, or used in
        # ``order_by`` / ``values``, is not; use ``with_lifecycle()`` (the
        # ``computed_status`` annotation) for those.
        extra = self._translate_lifecycle_kwargs(kwargs)
        if extra is not None:
            args = (*args, extra)
        return super()._filter_or_exclude(negate, args, kwargs)

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


class UrlNodeQuerySet(models.QuerySet):
    """QuerySet for :class:`~camomilla.models.page.UrlNode`.

    The default queryset is **lean** — no joins. ``UrlNode`` is the permalink
    uniqueness table, and most lookups (uniqueness checks, redirect resolution,
    simple permalink resolution) need only its own columns. Two opt-in,
    chainable methods add page data when a caller actually needs it:

    * :meth:`with_page` — ``select_related`` the concrete page row so
      ``node.page`` is free (no per-node query).
    * :meth:`with_lifecycle` — annotate ``is_public`` / ``status`` /
      ``published_at`` / ``deleted_at`` / ``indexable`` / ``date_updated_at``
      from the page, for SQL filtering / ordering and cheap scalar reads.

    Historically the *default* manager annotated unconditionally, forcing a
    LEFT JOIN to every concrete page table on every UrlNode query; these are
    now opt-in so the hot permalink/uniqueness paths stay join-free.
    """

    # The per-language ``date_updated_at`` default uses ``Value(now)``; resolved
    # once at build time, which is fine for an orphan-node fallback only.
    _LIFECYCLE_FIELD_SPECS = (
        ("indexable", BooleanField, None),
        ("published_at", DateTimeField, None),
        ("deleted_at", DateTimeField, None),
        ("date_updated_at", DateTimeField, "now"),
    )

    def _reverse_pages_relations(self):
        """Reverse one-to-one relations from each concrete ``AbstractPage``
        model back to this ``UrlNode`` — one per concrete page model. Returns
        ``[{"name": <accessor>, "model": <page model>}, ...]``."""
        from camomilla.models.page import AbstractPage

        relations = []
        for field in self.model._meta.get_fields():
            if not (hasattr(field, "related_model") and field.one_to_one):
                continue
            if not (
                field.related_model
                and issubclass(field.related_model, AbstractPage)
            ):
                continue
            if field.remote_field.name != "url_node":
                continue
            relations.append(
                {"name": field.get_accessor_name(), "model": field.related_model}
            )
        return relations

    def with_page(self):
        """``select_related`` every concrete reverse one-to-one page relation so
        ``node.page`` resolves from the relation cache. Reuses the joins
        :meth:`with_lifecycle` already creates, so chaining the two adds no
        joins — only the page columns. Use wherever ``node.page`` is read.
        """
        names = sorted({rel["name"] for rel in self._reverse_pages_relations()})
        return self.select_related(*names) if names else self

    def with_lifecycle(self):
        """Annotate the page-derived lifecycle fields onto each UrlNode:
        ``indexable`` / ``published_at`` / ``deleted_at`` / ``date_updated_at``
        (pulled from the **active-language** page column via
        ``localized_fieldname``), then the derived ``is_public`` / ``status``.

        Use this for SQL filtering/ordering (``.filter(is_public=True)``) and
        for cheap scalar reads without hydrating the whole page row.

        IMPORTANT — language: the active-language column is resolved at queryset
        **build** time, so the annotated values are only correct when the
        queryset is evaluated under the *same* active language it was built
        with. Camomilla's callers satisfy this (they run inside ``@active_lang``
        or activate the request language before building). For access-time,
        per-instance-correct values, read the page property instead
        (``node.page.is_public`` / ``node.page.status``).
        """
        relations_by_name = {
            rel["name"]: rel["model"] for rel in self._reverse_pages_relations()
        }
        names = sorted(relations_by_name)
        if not names:
            return self
        try:
            qs = self
            for field_name, output_cls, default_kind in self._LIFECYCLE_FIELD_SPECS:
                output_field = output_cls()
                default = (
                    Value(timezone.now(), output_cls())
                    if default_kind == "now"
                    else Value(None, output_cls())
                )
                whens = [
                    When(
                        related_name=name,
                        then=F(
                            "__".join(
                                [
                                    name,
                                    localized_fieldname(
                                        field_name, target=relations_by_name[name]
                                    ),
                                ]
                            )
                        ),
                    )
                    for name in names
                ]
                qs = qs.annotate(
                    **{
                        field_name: Case(
                            *whens, output_field=output_field, default=default
                        )
                    }
                )
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
                    When(published_at__isnull=False, then=Value(PAGE_STATUS_SCHEDULED)),
                    default=Value(PAGE_STATUS_DRAFT),
                    output_field=CharField(),
                ),
            )
        except (ProgrammingError, OperationalError):
            return self


class UrlNodeManager(models.Manager.from_queryset(UrlNodeQuerySet)):
    """Lean default manager for ``UrlNode`` — no joins on the default queryset.
    Opt into page data with ``.with_page()`` / ``.with_lifecycle()``."""
