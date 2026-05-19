from django import forms
from django.db import models as django_models
from camomilla import settings
from .translations import TranslationAwareModelAdmin
from camomilla.models import UrlNode

from camomilla.utils import get_templates


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


class AbstractPageAdmin(TranslationAwareModelAdmin):
    form = AbstractPageModelForm

    # Replace Django admin's ``AdminSplitDateTime`` (two free-text inputs,
    # one for date and one for time) with a single HTML5 ``datetime-local``
    # picker. ``formfield_overrides`` is the canonical hook: modeltranslation
    # builds per-language sibling fields by calling
    # ``DateTimeField.formfield()``, so the override applies uniformly to
    # ``published_at_<lang>`` / ``publish_at_<lang>`` without duplicating the
    # widget configuration per language.
    formfield_overrides = {
        django_models.DateTimeField: {
            "form_class": forms.DateTimeField,
            "widget": _datetime_local_widget(),
            "input_formats": _DATETIME_LOCAL_FORMATS,
        },
    }

    def get_form(self, request, obj=None, **kwargs):
        kwargs["form"] = self.form
        form = super().get_form(request, obj, **kwargs)

        class FormWithRequest(form):
            def __new__(cls, *args, **kwargs_):
                kwargs_["request"] = request
                return form(*args, **kwargs_)

        return FormWithRequest

    change_form_template = "admin/camomilla/page/change_form.html"
