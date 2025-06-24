from django.conf import settings as django_settings
from modeltranslation.settings import ENABLE_REGISTRATIONS, AVAILABLE_LANGUAGES

from camomilla.utils.getters import pointed_getter

PROJECT_TITLE = pointed_getter(
    django_settings,
    "CAMOMILLA.PROJECT_TITLE",
    pointed_getter(django_settings, "CAMOMILLA_PROJECT_TITLE", "Camomilla"),
)

THUMBNAIL_FOLDER = pointed_getter(
    django_settings,
    "CAMOMILLA.MEDIA.THUMBNAIL.FOLDER",
    pointed_getter(django_settings, "CAMOMILLA_THUMBTHUMBNAIL_FOLDER", "thumbnails"),
)
THUMBNAIL_WIDTH = pointed_getter(
    django_settings,
    "CAMOMILLA.MEDIA.THUMBNAIL.WIDTH",
    pointed_getter(django_settings, "CAMOMILLA_THUMBNAIL_WIDTH", 50),
)
THUMBNAIL_HEIGHT = pointed_getter(
    django_settings,
    "CAMOMILLA.MEDIA.THUMBNAIL.HEIGHT",
    pointed_getter(django_settings, "CAMOMILLA_THUMBNAIL_HEIGHT", 50),
)
BASE_URL = pointed_getter(
    django_settings,
    "CAMOMILLA.ROUTER.BASE_URL",
    pointed_getter(django_settings, "FORCE_SCRIPT_NAME", None),
)
BASE_URL = BASE_URL and "/" + BASE_URL.strip("/")


ARTICLE_DEFAULT_TEMPLATE = pointed_getter(
    django_settings,
    "CAMOMILLA.RENDER.ARTICLE.DEFAULT_TEMPLATE",
    "defaults/articles/default.html",
)
PAGE_DEFAULT_TEMPLATE = pointed_getter(
    django_settings,
    "CAMOMILLA.RENDER.PAGE.DEFAULT_TEMPLATE",
    "defaults/pages/default.html",
)
ARTICLE_INJECT_CONTEXT_FUNC = pointed_getter(
    django_settings, "CAMOMILLA.RENDER.ARTICLE.INJECT_CONTEXT", None
)
PAGE_INJECT_CONTEXT_FUNC = pointed_getter(
    django_settings, "CAMOMILLA.RENDER.PAGE.INJECT_CONTEXT", None
)

PAGES_DEFAULT_SERIALIZER = pointed_getter(
    django_settings,
    "CAMOMILLA.API.PAGES.DEFAULT_SERIALIZER",
    "camomilla.serializers.mixins.AbstractPageMixin",
)

ENABLE_TRANSLATIONS = (
    ENABLE_REGISTRATIONS and "modeltranslation" in django_settings.INSTALLED_APPS
)

DEFAULT_LANGUAGE = pointed_getter(django_settings, "LANGUAGE_CODE", "en")

LANGUAGE_CODES = AVAILABLE_LANGUAGES

MEDIA_OPTIMIZE_MAX_WIDTH = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.OPTIMIZE.MAX_WIDTH", 1980
)
MEDIA_OPTIMIZE_MAX_HEIGHT = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.OPTIMIZE.MAX_HEIGHT", 1400
)
MEDIA_OPTIMIZE_DPI = pointed_getter(django_settings, "CAMOMILLA.MEDIA.OPTIMIZE.DPI", 30)

MEDIA_OPTIMIZE_JPEG_QUALITY = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.OPTIMIZE.JPEG_QUALITY", 85
)

ENABLE_MEDIA_OPTIMIZATION = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.OPTIMIZE.ENABLE", True
)

API_NESTING_DEPTH = pointed_getter(django_settings, "CAMOMILLA.API.NESTING_DEPTH", 10)

AUTO_CREATE_HOMEPAGE = pointed_getter(
    django_settings, "CAMOMILLA.RENDER.AUTO_CREATE_HOMEPAGE", True
)

TEMPLATE_CONTEXT_FILES = pointed_getter(
    django_settings, "CAMOMILLA.RENDER.TEMPLATE_CONTEXT_FILES", []
)

API_TRANSLATION_ACCESSOR = pointed_getter(
    django_settings, "CAMOMILLA.API.TRANSLATION_ACCESSOR", "translations"
)

REGISTERED_TEMPLATES_APPS = pointed_getter(
    django_settings, "CAMOMILLA.RENDER.REGISTERED_TEMPLATES_APPS", None
)

INTEGRATIONS_ASTRO_ENABLE = pointed_getter(
    django_settings, "CAMOMILLA.INTEGRATIONS.ASTRO.ENABLE", False
)

INTEGRATIONS_ASTRO_URL = pointed_getter(
    django_settings, "CAMOMILLA.INTEGRATIONS.ASTRO.URL", ""
)

DEBUG = pointed_getter(django_settings, "CAMOMILLA.DEBUG", django_settings.DEBUG)

# camomilla settings example
# CAMOMILLA = {
#     "PROJECT_TITLE": "",
#     "ROUTER": {
#         "BASE_URL": ""
#     },
#     "MEDIA": {
#         "OPTIMIZE": {"MAX_WIDTH": 1980, "MAX_HEIGHT": 1400, "DPI": 30, "JPEG_QUALITY": 85, "ENABLE": True},
#         "THUMBNAIL": {"FOLDER": "", "WIDTH": 50, "HEIGHT": 50}
#     },
#     "RENDER": {
#         "TEMPLATE_CONTEXT_FILES": [],
#         "AUTO_CREATE_HOMEPAGE": True,
#         "ARTICLE": {"DEFAULT_TEMPLATE": "", "INJECT_CONTEXT": None },
#         "PAGE": {"DEFAULT_TEMPLATE": "", "INJECT_CONTEXT": None }
#         "REGISTERED_TEMPLATE_APPS": []
#     },
#     "STRUCTURED_FIELD": {
#         "CACHE_ENABLED": True
#     }
#     "INTEGRATIONS": {
#         "ASTRO": {
#             "ENABLE": True,
#             "URL": "http://localhost:4321"
#         }
#     }
#     "API": {"NESTING_DEPTH": 10, "TRANSLATION_ACCESSOR": "translations", "PAGES": {"DEFAULT_SERIALIZER": "camomilla.serializers.page.RouteSerializer"}},
#     "DEBUG": False
# }
