from django import forms
from django.contrib import admin, messages
from django.db import models as django_models
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from camomilla import settings
from camomilla.models import UrlNode
from camomilla.models.draft import Draft
from camomilla.models.page import (
    PAGE_STATUS_DRAFT,
    PAGE_STATUS_PUBLISHED,
    PAGE_STATUS_SCHEDULED,
    PAGE_STATUS_TRASHED,
)
from camomilla.preview import reversion_available
from camomilla.utils import get_templates

from .translations import TranslationAwareModelAdmin


# --- reversion + translation admin base -----------------------------------
#
# We need BOTH ``modeltranslation.admin.TabbedTranslationAdmin`` (so the
# base-column / per-language-column duplication is properly hidden in the
# form) AND ``reversion.admin.VersionAdmin`` (so editors get the built-in
# revisions browser + revert UI without us shipping a custom history view).
# Compose them here so subclasses only need to inherit a single base. When
# reversion isn't installed, fall back to the translation-aware admin alone.
if reversion_available():
    from reversion.admin import VersionAdmin

    class _RevisionsAdminBase(VersionAdmin, TranslationAwareModelAdmin):
        """``VersionAdmin`` first in MRO — it overrides ``history_view`` and
        ``response_change`` to wire reversion in, but defers everything else
        to ``super()``, which lands on ``TabbedTranslationAdmin`` so its
        ``get_form`` / ``get_fieldsets`` still hide the base translatable
        columns."""
else:  # pragma: no cover
    _RevisionsAdminBase = TranslationAwareModelAdmin


# HTML5 datetime-local input formats — browsers emit ``YYYY-MM-DDTHH:MM``
# without seconds, but Django's default DateTimeField parser only accepts
# the seconds-bearing variants. Listing both lets the form round-trip
# values that arrive from any modern browser.
_DATETIME_LOCAL_FORMATS = (
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
)


def _datetime_local_widget() -> forms.DateTimeInput:
    return forms.DateTimeInput(
        attrs={"type": "datetime-local"},
        format=_DATETIME_LOCAL_FORMATS[0],
    )


# --- lifecycle badge palette ------------------------------------------------
# Inline-styled tiny badges. We avoid a stylesheet to keep theming options
# open and to keep the admin auto-loadable without static-collection.
_STATUS_BADGE = {
    PAGE_STATUS_PUBLISHED: ("#28a745", _("Published")),
    PAGE_STATUS_DRAFT: ("#6c757d", _("Draft")),
    PAGE_STATUS_SCHEDULED: ("#fd7e14", _("Scheduled")),
    PAGE_STATUS_TRASHED: ("#dc3545", _("Trashed")),
}


class LifecycleStatusFilter(admin.SimpleListFilter):
    """Sidebar filter for the computed ``status`` property.

    ``status`` is a per-language derivation of the timestamp triple, not a
    stored column, so we wire each option to the corresponding queryset
    helper instead of a raw ``__exact`` lookup. The helpers already cope
    with monolingual + multilingual setups via ``modeltranslation`` auto-
    rewrites in filter context.
    """

    title = _("Lifecycle status")
    parameter_name = "lifecycle"

    def lookups(self, request, model_admin):
        return tuple((code, label) for code, (_color, label) in _STATUS_BADGE.items())

    def queryset(self, request, queryset):
        value = self.value()
        if value == PAGE_STATUS_PUBLISHED:
            return queryset.public()
        if value == PAGE_STATUS_SCHEDULED:
            return queryset.alive().scheduled()
        if value == PAGE_STATUS_TRASHED:
            return queryset.trashed()
        if value == PAGE_STATUS_DRAFT:
            # Alive, never publicly visible — "true draft" bucket.
            return queryset.alive().filter(published_at__isnull=True)
        return queryset


class AbstractPageModelFormMeta(forms.models.ModelFormMetaclass):
    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)
        fields_to_add = forms.fields_for_model(UrlNode, UrlNode.LANG_PERMALINK_FIELDS)
        if settings.ENABLE_TRANSLATIONS:
            for i, field_name in enumerate(fields_to_add.keys()):
                field_classes = ["mt", f"mt-field-{field_name.replace('_', '-')}"]
                i == 0 and field_classes.append("mt-default")
                fields_to_add[field_name].widget.attrs.update(
                    {"class": " ".join(field_classes)}
                )
        new_class.base_fields.update(fields_to_add)
        return new_class


class AbstractPageModelForm(
    forms.models.BaseModelForm, metaclass=AbstractPageModelFormMeta
):
    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        templates = [(t, t) for t in get_templates(request)]
        templates.insert(0, ("", "---------"))
        self.fields["template"] = forms.ChoiceField(choices=templates, required=False)

    def get_initial_for_field(self, field, field_name):
        if field_name in UrlNode.LANG_PERMALINK_FIELDS:
            return getattr(self.instance, field_name)
        return super().get_initial_for_field(field, field_name)

    def save(self, commit: bool = True):
        model = super().save(commit=False)
        for field_name in UrlNode.LANG_PERMALINK_FIELDS:
            if field_name in self.cleaned_data:
                if getattr(model, field_name) != self.cleaned_data[field_name]:
                    # sets autopermalink to False if permalink is manually set
                    setattr(model, f"auto{field_name}", False)
                setattr(model, field_name, self.cleaned_data[field_name])
        if commit:
            model.save()
        return model


class AbstractPageAdmin(_RevisionsAdminBase):
    form = AbstractPageModelForm

    # Replace Django admin's ``AdminSplitDateTime`` (two free-text inputs,
    # one for date and one for time) with a single HTML5 ``datetime-local``
    # picker. ``formfield_overrides`` is the canonical hook: modeltranslation
    # builds per-language sibling fields by calling
    # ``DateTimeField.formfield()``, so the override applies uniformly to
    # ``published_at_<lang>`` without duplicating the widget per language.
    formfield_overrides = {
        django_models.DateTimeField: {
            "form_class": forms.DateTimeField,
            "widget": _datetime_local_widget(),
            "input_formats": _DATETIME_LOCAL_FORMATS,
        },
    }

    # Lifecycle is at-a-glance from the list view: status badge first, then
    # the draft pen, then ordering for drag-handles.
    list_display = (
        "__str__",
        "lifecycle_badge",
        "has_draft_indicator",
        "ordering",
    )
    list_filter = (LifecycleStatusFilter,)
    actions = ("admin_publish_now", "admin_trash", "admin_restore")

    # ------------------------------------------------------------------
    # list-view columns
    # ------------------------------------------------------------------

    @admin.display(description=_("Status"))
    def lifecycle_badge(self, obj):
        """Coloured pill showing the current lifecycle label.

        The label is read from the in-memory property, which is language-
        aware via :func:`get_nofallbacks` — so an editor browsing the
        admin in EN sees EN's lifecycle, not whatever happens to be in
        the base column. Consistent with the rest of the admin (every
        translatable field is shown per-active-language).
        """
        color, label = _STATUS_BADGE.get(obj.status, ("#888", obj.status))
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            'background:{};color:#fff;font-size:11px;font-weight:600;">{}</span>',
            color,
            label,
        )

    @admin.display(description=_("Draft"), boolean=True)
    def has_draft_indicator(self, obj):
        """True when a Draft row exists in the active language."""
        return Draft.objects.for_(obj, language=obj._draft_language()).exists()

    # ------------------------------------------------------------------
    # read-only Draft Inspector — see what is pending per language
    # ------------------------------------------------------------------

    def _collect_draft_diff(self, obj) -> list:
        """Build a per-language ``{field: (live, draft)}`` diff for ``obj``.

        Mirrors the django-reversion philosophy: the admin only *observes*
        the staged state and acts on it (publish / discard). It does not
        author drafts — that path lives on the ``/draft/`` API endpoint.

        Walks every :class:`Draft` row attached to ``obj`` and pairs each
        entry in ``draft.serialized`` with the corresponding live value:

        * Translatable keys (``draft["translations"][lang]``) compare
          against the per-language column (``title_<lang>``).
        * Top-level non-translatable keys (``ordering``, ``template``)
          compare against the unsuffixed model attribute.

        Returns ``[(lang, [(field, live_value, draft_value), ...]), ...]``;
        empty list when nothing is pending.
        """
        from camomilla.settings import API_TRANSLATION_ACCESSOR
        from camomilla.utils.translation import localized_fieldname

        diffs = []
        for draft in Draft.objects.for_(obj).order_by("language"):
            payload = draft.serialized if isinstance(draft.serialized, dict) else {}
            if not payload:
                continue
            lang = draft.language or None
            rows = []
            translations = payload.get(API_TRANSLATION_ACCESSOR) or {}
            lang_translations = (
                translations.get(lang, {}) if isinstance(translations, dict) else {}
            )
            for key, draft_val in lang_translations.items():
                live_field = (
                    localized_fieldname(key, language=lang, target=obj)
                    if lang
                    else key
                )
                live_val = getattr(obj, live_field, None)
                rows.append((key, live_val, draft_val))

            for key, draft_val in payload.items():
                if key == API_TRANSLATION_ACCESSOR:
                    continue
                live_val = getattr(obj, key, None)
                rows.append((key, live_val, draft_val))

            if rows:
                diffs.append((lang or "—", rows))
        return diffs

    # ------------------------------------------------------------------
    # custom admin URLs for single-object lifecycle actions
    # ------------------------------------------------------------------

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "<path:object_id>/publish/",
                self.admin_site.admin_view(self.publish_view),
                name="%s_%s_publish" % info,
            ),
            path(
                "<path:object_id>/discard-draft/",
                self.admin_site.admin_view(self.discard_draft_view),
                name="%s_%s_discard_draft" % info,
            ),
            path(
                "<path:object_id>/trash/",
                self.admin_site.admin_view(self.trash_view),
                name="%s_%s_trash" % info,
            ),
            path(
                "<path:object_id>/restore/",
                self.admin_site.admin_view(self.restore_view),
                name="%s_%s_restore" % info,
            ),
        ]
        return custom + super().get_urls()

    def _change_url(self, object_id):
        info = self.model._meta.app_label, self.model._meta.model_name
        return reverse("admin:%s_%s_change" % info, args=(object_id,))

    def _changelist_url(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return reverse("admin:%s_%s_changelist" % info)

    def publish_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponseRedirect(self._changelist_url())
        obj.publish(comment="Published from admin")
        messages.success(request, _("Page published."))
        return HttpResponseRedirect(self._change_url(object_id))

    def discard_draft_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponseRedirect(self._changelist_url())
        obj.discard_draft()
        messages.success(request, _("Draft discarded."))
        return HttpResponseRedirect(self._change_url(object_id))

    def trash_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponseRedirect(self._changelist_url())
        obj.trash()
        messages.success(request, _("Page moved to trash."))
        return HttpResponseRedirect(self._change_url(object_id))

    def restore_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponseRedirect(self._changelist_url())
        obj.restore()
        messages.success(request, _("Page restored from trash."))
        return HttpResponseRedirect(self._change_url(object_id))

    # ------------------------------------------------------------------
    # bulk actions
    # ------------------------------------------------------------------

    @admin.action(description=_("Publish selected pages now"))
    def admin_publish_now(self, request, queryset):
        count = 0
        for page in queryset:
            page.publish(comment="Bulk publish from admin")
            count += 1
        messages.success(request, _("Published %(n)d page(s).") % {"n": count})

    @admin.action(description=_("Move selected pages to trash"))
    def admin_trash(self, request, queryset):
        count = queryset.alive().count()
        for page in queryset.alive():
            page.trash()
        messages.success(request, _("Trashed %(n)d page(s).") % {"n": count})

    @admin.action(description=_("Restore selected pages from trash"))
    def admin_restore(self, request, queryset):
        count = queryset.trashed().count()
        for page in queryset.trashed():
            page.restore()
        messages.success(request, _("Restored %(n)d page(s).") % {"n": count})

    # ------------------------------------------------------------------
    # change-form integration
    # ------------------------------------------------------------------

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = self.form
        form = super().get_form(request, obj, **kwargs)

        class FormWithRequest(form):
            def __new__(cls, *args, **kwargs_):
                kwargs_["request"] = request
                return form(*args, **kwargs_)

        return FormWithRequest

    def render_change_form(self, request, context, *args, **kwargs):
        """Surface lifecycle action URLs to the change_form template.

        Computed here (not in the template) so the template stays a thin
        rendering layer and the URL-name plumbing stays in one place.
        """
        obj = context.get("original")
        info = self.model._meta.app_label, self.model._meta.model_name
        if obj is not None and obj.pk:
            color, label = _STATUS_BADGE.get(obj.status, ("#888", obj.status))
            context.update(
                {
                    "lifecycle_status": obj.status,
                    "lifecycle_status_label": label,
                    "lifecycle_status_color": color,
                    "lifecycle_has_draft": Draft.objects.for_(obj).exists(),
                    "lifecycle_is_trashed": obj.deleted_at is not None,
                    "lifecycle_draft_diff": self._collect_draft_diff(obj),
                    "lifecycle_render_url": _render_url_for(obj),
                    "lifecycle_publish_url": reverse(
                        "admin:%s_%s_publish" % info, args=(obj.pk,)
                    ),
                    "lifecycle_discard_draft_url": reverse(
                        "admin:%s_%s_discard_draft" % info, args=(obj.pk,)
                    ),
                    "lifecycle_trash_url": reverse(
                        "admin:%s_%s_trash" % info, args=(obj.pk,)
                    ),
                    "lifecycle_restore_url": reverse(
                        "admin:%s_%s_restore" % info, args=(obj.pk,)
                    ),
                }
            )
        return super().render_change_form(request, context, *args, **kwargs)

    change_form_template = "admin/camomilla/page/change_form.html"


def _render_url_for(obj):
    """Return the authenticated ``/render/`` URL for ``obj``, or ``None``.

    Only the ``Page`` viewset is registered with the preview action — other
    ``AbstractPage`` subclasses (e.g. ``Article``) inherit the admin
    machinery but would need their own viewset to expose a preview link.
    Guard accordingly so we never surface a link that would 404 on click.
    """
    from django.urls import NoReverseMatch
    from camomilla.models import Page

    if obj is None or not isinstance(obj, Page):
        return None
    try:
        return reverse("camomilla-pages-render-preview", args=(obj.pk,))
    except NoReverseMatch:
        return None
