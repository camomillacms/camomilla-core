from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django import forms
from django.contrib import admin
from django.http import HttpResponse

from camomilla import settings

if settings.ENABLE_TRANSLATIONS:
    from modeltranslation.admin import (
        TabbedTranslationAdmin as TranslationAwareModelAdmin,
    )
else:
    from django.contrib.admin import ModelAdmin as TranslationAwareModelAdmin

from camomilla.models import Article, Content, Media, MediaFolder, Page, Tag, Menu


class AbstractPageAdmin(TranslationAwareModelAdmin):
    change_form_template = "admin/camomilla/page/change_form.html"


class UserProfileAdmin(admin.ModelAdmin):
    pass


class ArticleAdminForm(forms.ModelForm):
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
    readonly_fields = ("permalink",)


class MenuAdmin(TranslationAwareModelAdmin):
    pass


admin.site.register(Article, ArticleAdmin)
admin.site.register(MediaFolder, MediaFolderAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Content, ContentAdmin)
admin.site.register(Media, MediaAdmin)
admin.site.register(Page, PageAdmin)
admin.site.register(Menu, MenuAdmin)
