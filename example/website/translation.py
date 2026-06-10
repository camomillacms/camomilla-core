"""Per-app modeltranslation registrations.

Only concrete ``AbstractPage`` subclasses that materialise their own
table need to be registered here — the columns inherited from
``AbstractPage`` aren't translatable on the subclass's table unless we
declare them so. Registering ``HomePage`` materialises its
``title_en`` / ``title_it`` / ``template_data_en`` / ``template_data_it``
(etc.) columns the same way camomilla's own ``PageTranslationOptions``
does for ``Page``.
"""

from modeltranslation.translator import register

from camomilla.translation import AbstractPageTranslationOptions

from .models import HomePage


@register(HomePage)
class HomePageTranslationOptions(AbstractPageTranslationOptions):
    pass
