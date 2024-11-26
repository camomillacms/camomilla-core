from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from django.http import HttpResponse
from modeltranslation.translator import translator

from camomilla import settings
from camomilla.utils.translation import get_field_translation_accessors

if settings.ENABLE_TRANSLATIONS:
    from modeltranslation.admin import (
        TabbedTranslationAdmin as TranslationAwareModelAdmin,
    )
else:
    from django.contrib.admin import ModelAdmin as TranslationAwareModelAdmin

from camomilla.models import Article, Content, Media, MediaFolder, Page, Tag, Menu, UrlRedirect, UrlNode


class AbstractPageModelFormMeta(forms.models.ModelFormMetaclass):
    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)
        if not settings.ENABLE_TRANSLATIONS:
            return new_class
        permalink_fields = forms.fields_for_model(UrlNode, get_field_translation_accessors("permalink"))
        new_class.base_fields.update(permalink_fields)
        return new_class



class AbstractPageModelForm(forms.models.BaseModelForm, metaclass=AbstractPageModelFormMeta):
    def get_initial_for_field(self, field,field_name):
        if settings.ENABLE_TRANSLATIONS and field_name in get_field_translation_accessors("permalink"):
            return getattr(self.instance, field_name)
        return super().get_initial_for_field(field, field_name)
    
    def save(self, commit:bool = True):
        if not settings.ENABLE_TRANSLATIONS:
            return super().save(commit=commit)
        model = super().save(commit=False)
        for field_name in get_field_translation_accessors("permalink"):
            if field_name in self.cleaned_data:
                setattr(model, field_name, self.cleaned_data[field_name])
        if commit:
            model.save()
        return model


class AbstractPageAdmin(TranslationAwareModelAdmin):
    form = AbstractPageModelForm
    change_form_template = "admin/camomilla/page/change_form.html"
    
    
    def __init__(self, *args, **kwargs):
        if not settings.ENABLE_TRANSLATIONS:
            return super().__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)
        fields_to_add = [get_field_translation_accessors("permalink"), "permalink"]
        for name, field in translator.get_options_for_model(UrlNode).fields.items():
            if name in fields_to_add:
                self.trans_opts.fields.update({name: field})


class UserProfileAdmin(admin.ModelAdmin):
    pass

class ArticleAdminForm(AbstractPageModelForm):
    class Meta:
        model = Article
        fields = "__all__"
        widgets = {"content": CKEditorUploadingWidget}


class ArticleAdmin(AbstractPageAdmin):
    filter_horizontal = ("tags",)
    form = ArticleAdminForm


class TagAdmin(TranslationAwareModelAdmin):
    pass


class MediaFolderAdmin(admin.ModelAdmin):
    readonly_fields = ("path",)


class ContentAdminForm(forms.ModelForm):
    class Meta:
        model = Content
        fields = "__all__"
        widgets = {"content": CKEditorUploadingWidget}


class ContentAdmin(TranslationAwareModelAdmin):
    form = ContentAdminForm


class MediaAdmin(TranslationAwareModelAdmin):
    exclude = (
        "thumbnail",
        "size",
        "image_props",
    )
    readonly_fields = ("image_preview", "image_thumb_preview", "mime_type")
    list_display = (
        "__str__",
        "title",
        "image_thumb_preview",
    )

    def response_add(self, request, obj):
        if request.GET.get("_popup", ""):
            return HttpResponse(
                """
               <script type="text/javascript">
                  opener.dismissAddRelatedObjectPopup(window, %s, '%s');
               </script>"""
                % (obj.id, obj.json_repr)
            )
        else:
            return super(MediaAdmin, self).response_add(request, obj)


class PageAdmin(AbstractPageAdmin):
    # readonly_fields = ("permalink",)
    pass


class MenuAdmin(TranslationAwareModelAdmin):
    pass


class UrlRedirectAdmin(admin.ModelAdmin):
    pass


admin.site.register(Article, ArticleAdmin)
admin.site.register(MediaFolder, MediaFolderAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Content, ContentAdmin)
admin.site.register(Media, MediaAdmin)
admin.site.register(Page, PageAdmin)
admin.site.register(Menu, MenuAdmin)
admin.site.register(UrlRedirect, UrlRedirectAdmin)
