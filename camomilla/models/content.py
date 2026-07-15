from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from djsuperadmin.mixins import DjSuperAdminMixin


class AbstractContent(DjSuperAdminMixin, models.Model):
    identifier = models.CharField(max_length=255)
    content = models.TextField(default="")
    content_type = models.ForeignKey(
        ContentType, blank=True, null=True, on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(blank=True, null=True)
    page = GenericForeignKey("content_type", "object_id")

    @property
    def superadmin_get_url(self):
        return reverse("camomilla-content-djsuperadmin", kwargs={"pk": self.pk})

    @property
    def superadmin_patch_url(self):
        return reverse("camomilla-content-djsuperadmin", kwargs={"pk": self.pk})

    @property
    def superadmin_history_url(self):
        return reverse("camomilla-content-djsuperadmin-history", kwargs={"pk": self.pk})

    class Meta:
        abstract = True
        unique_together = ["identifier", "content_type", "object_id"]

    def __str__(self):
        if len(self.identifier) > 40:
            return "%s..." % self.identifier[:40]
        return self.identifier


class Content(AbstractContent):
    pass


class AbstractContentVersion(models.Model):
    """A previous value of a Content, snapshotted before it was overwritten so a
    djsuperadmin edit can be reverted (mirrors the pip package's history)."""

    content = models.ForeignKey(
        Content, related_name="versions", on_delete=models.CASCADE
    )
    data = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at", "-id"]


class ContentVersion(AbstractContentVersion):
    pass
