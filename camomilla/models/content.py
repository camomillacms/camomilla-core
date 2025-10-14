from django.db import models
from django.urls import reverse
from djsuperadmin.mixins import DjSuperAdminMixin


class AbstractContent(DjSuperAdminMixin, models.Model):
    identifier = models.CharField(max_length=255)
    content = models.TextField(default="")
    page = models.ForeignKey(
        "camomilla.Page",
        blank=False,
        null=True,
        on_delete=models.SET_NULL,
        related_name="contents",
    )

    @property
    def superadmin_get_url(self):
        return reverse("camomilla-content-djsuperadmin", kwargs={"pk": self.pk})

    @property
    def superadmin_patch_url(self):
        return reverse("camomilla-content-djsuperadmin", kwargs={"pk": self.pk})

    class Meta:
        abstract = True
        unique_together = ["identifier", "page"]

    def __str__(self):
        if len(self.identifier) > 40:
            return "%s..." % self.identifier[:40]
        return self.identifier


class Content(AbstractContent):
    pass
