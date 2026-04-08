from django import forms
from django.contrib import admin
from structured.widget.fields import StructuredJSONFormField

from camomilla.models import MetaInstance, MetaType


class MetaTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "key")
    prepopulated_fields = {"key": ("name",)}


class MetaInstanceForm(forms.ModelForm):
    class Meta:
        model = MetaInstance
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        meta_type = None
        if self.instance and self.instance.pk:
            meta_type = self.instance.meta_type
        else:
            initial_mt = self.initial.get("meta_type") or self.data.get("meta_type")
            if initial_mt:
                meta_type = MetaType.objects.filter(pk=initial_mt).first()
        if meta_type is not None:
            schema_cls = meta_type.get_pydantic_model()
            self.fields["data"] = StructuredJSONFormField(
                schema=schema_cls, required=False
            )
        else:
            self.fields["data"].help_text = (
                "Select a meta type and save to start editing the data."
            )


class MetaInstanceAdmin(admin.ModelAdmin):
    form = MetaInstanceForm
    list_display = ("__str__", "meta_type", "updated_at")
    list_filter = ("meta_type",)
    search_fields = ("identifier",)

    class Media:
        js = ("camomilla/admin/meta_instance.js",)
