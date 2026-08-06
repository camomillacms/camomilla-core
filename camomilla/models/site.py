from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from camomilla.models.content import Content
from camomilla.models.menu import Menu

__all__ = ["SiteEpoch"]


class SiteEpoch(models.Model):
    """Single-row monotonic marker, bumped whenever a *global* render input
    changes — a menu, or a page-less (global) Content block.
    """

    SINGLETON_PK = 1
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def bump(cls) -> None:
        obj, created = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        if not created:
            obj.save()  # refresh auto_now

    @classmethod
    def current(cls):
        obj = cls.objects.filter(pk=cls.SINGLETON_PK).first()
        return obj.updated_at if obj else None


@receiver(post_save, sender=Menu, dispatch_uid="site_epoch_menu_save")
@receiver(post_delete, sender=Menu, dispatch_uid="site_epoch_menu_delete")
def _bump_epoch_on_menu(sender, instance, **kwargs):
    SiteEpoch.bump()


@receiver(post_save, sender=Content, dispatch_uid="site_epoch_content_save")
@receiver(post_delete, sender=Content, dispatch_uid="site_epoch_content_delete")
def _bump_epoch_on_global_content(sender, instance, **kwargs):
    # Content without an object_id is a global block, not a page-scoped one. Complete bump is needed.
    if instance.object_id is None:
        SiteEpoch.bump()
