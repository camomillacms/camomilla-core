from camomilla import settings

if settings.ENABLE_TRANSLATIONS:
    from modeltranslation.admin import (
        TabbedTranslationAdmin as TranslationAwareModelAdmin,
    )
else:
    from django.contrib.admin import ModelAdmin as TranslationAwareModelAdmin


__all__ = [
    "TranslationAwareModelAdmin",
]
