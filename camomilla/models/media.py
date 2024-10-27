import json
import os
from io import BytesIO

import magic
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from PIL import Image

from camomilla.fields import JSONField
from camomilla.settings import THUMBNAIL_FOLDER, THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from camomilla.storages.optimize import OptimizedStorage


class AbstractMediaFolder(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(editable=False, max_length=200, blank=True, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    path = models.TextField(blank=True, null=True, editable=False)
    updir = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="child_folders",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def update_childs(self):
        for folder in self.child_folders.all():
            folder.save()

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        if self.updir:
            if self.updir.id == self.id:
                raise ValidationError({"updir": "Unvalid parent"})
            self.path = "{0}/{1}".format(self.updir.path, self.slug)
        else:
            self.path = "/{0}".format(self.slug)

        super().save(*args, **kwargs)
        self.update_childs()

    def __str__(self):
        return "[%s] %s" % (self.__class__.__name__, self.title)


class MediaFolder(AbstractMediaFolder):
    pass


class Media(models.Model):
    # Seo Attributes
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    file = models.FileField(storage=OptimizedStorage())
    thumbnail = models.ImageField(
        upload_to=THUMBNAIL_FOLDER,
        max_length=500,
        null=True,
        blank=True,
    )
    created = models.DateTimeField(auto_now=True)
    size = models.IntegerField(default=0, blank=True, null=True, editable=False)
    mime_type = models.CharField(max_length=128, blank=True, null=True, editable=False)
    image_props = JSONField(default=dict, blank=True, editable=False)
    folder = models.ForeignKey(
        MediaFolder,
        null=True,
        blank=True,
        related_name="media_folder",
        on_delete=models.CASCADE,
    )

    @property
    def path(self):
        return "%s/%s" % (self.folder.path, self.name)

    @property
    def is_image(self):
        return self.mime_type and self.mime_type.startswith("image")

    def image_preview(self):
        if self.file:
            return mark_safe('<img src="{0}" />'.format(self.file.url))

    def image_thumb_preview(self):
        if self.thumbnail:
            return mark_safe('<img src="{0}" />'.format(self.thumbnail.url))

    image_preview.short_description = _("Preview")
    image_thumb_preview.short_description = _("Thumbnail")

    class Meta:
        ordering = ["-pk"]

    def regenerate_thumbnail(self):
        self._remove_thumbnail()
        if self.file:
            self._make_thumbnail()

    def get_foreign_fields(self):
        return [
            field.get_accessor_name()
            for field in self._meta.get_fields()
            if issubclass(type(field), ForeignObjectRel)
        ]

    @property
    def json_repr(self):
        json_r = {
            "id": self.pk,
            "thumbnail": "" if not self.is_image else self.thumbnail.url,
            "label": self.__str__(),
        }
        return json.dumps(json_r)

    def _update_file_info(self, img_bytes=None):
        try:
            if not img_bytes:
                img_bytes = self.file.storage.open(self.file.name, "rb")
            self.mime_type = magic.from_buffer(img_bytes.read(2048), mime=True)
            with Image.open(img_bytes) as image:
                self.image_props = {
                    "width": image.width,
                    "height": image.height,
                    "format": image.format,
                    "mode": image.mode,
                }
        except Exception as ex:
            print(ex)
            return False

    def _make_thumbnail(self, img_bytes=None):
        try:
            if not img_bytes:
                img_bytes = self.file.storage.open(self.file.name, "rb")
            with Image.open(img_bytes) as orig_image:
                image = orig_image.copy()
                image.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.LANCZOS)

                # Path to save to, name, and extension
                thumb_name, thumb_extension = os.path.splitext(self.file.name)
                thumb_extension = thumb_extension.lower()
                thumb_filename = thumb_name + "_thumb" + thumb_extension
                temp_thumb = BytesIO()
                image.save(temp_thumb, "PNG", optimize=True)
                temp_thumb.seek(0)
                # Load a ContentFile into the thumbnail field so it gets saved
                self.thumbnail.save(
                    thumb_filename, ContentFile(temp_thumb.read()), save=False
                )
                temp_thumb.close()
        except Exception:
            return False

        return True

    def _remove_file(self):
        if self.file:
            self.file.storage.delete(self.file.name)

    def _remove_thumbnail(self):
        if self.thumbnail:
            self.thumbnail.storage.delete(self.thumbnail.name)

    def _get_file_size(self):
        try:
            return self.file.storage.size(self.file.name)
        except Exception:
            return 0

    def __str__(self):
        if self.title:
            return self.title
        return self.file.name


@receiver(post_save, sender=Media, dispatch_uid="make thumbnails")
def update_media(sender, instance: Media, **kwargs):
    instance._remove_thumbnail()
    image_bytes = instance.file.storage.open(instance.file.name, "rb")
    instance._update_file_info(image_bytes)
    instance._make_thumbnail(image_bytes)
    Media.objects.filter(pk=instance.pk).update(
        size=instance._get_file_size(),
        thumbnail=instance.thumbnail,
        mime_type=instance.mime_type,
        image_props=instance.image_props,
    )


@receiver(pre_delete, sender=Media, dispatch_uid="make thumbnails")
def delete_media_files(sender, instance: Media, **kwargs):
    instance._remove_thumbnail()
    instance._remove_file()
