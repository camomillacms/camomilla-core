from django.db import models


class SeoMixin(models.Model):
    title = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    og_description = models.TextField(blank=True, null=True)
    og_title = models.CharField(max_length=200, blank=True, null=True)
    og_type = models.CharField(max_length=200, blank=True, null=True)
    og_url = models.CharField(max_length=200, blank=True, null=True)
    canonical = models.CharField(max_length=200, blank=True, null=True)
    og_image = models.ForeignKey(
        "camomilla.Media",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_og_images",
    )
    keywords = models.JSONField(default=list)

    class Meta:
        abstract = True


class MetaMixin(models.Model):
    meta = models.JSONField(default=dict, null=False, blank=True)

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def update_meta(self, key, value):
        self.meta[key] = value
        super(MetaMixin, self).save(update_fields=["meta"])

    def delete_meta(self, key):
        del self.meta[key]
        super(MetaMixin, self).save(update_fields=["meta"])

    class Meta:
        abstract = True
