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

MEDIA_RENDITIONS_ENABLE = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.ENABLE", True
)

MEDIA_RENDITIONS_CONFIG = pointed_getter(
    django_settings,
    "CAMOMILLA.MEDIA.RENDITIONS.VARIANTS",
    [
        {"name": "sm-webp", "width": 400, "format": "webp"},
        {"name": "md-webp", "width": 800, "format": "webp"},
        {"name": "lg-webp", "width": 1600, "format": "webp"},
        {"name": "sm-avif", "width": 400, "format": "avif"},
        {"name": "md-avif", "width": 800, "format": "avif"},
        {"name": "lg-avif", "width": 1600, "format": "avif"},
        {"name": "sm-original", "width": 400, "format": "original"},
        {"name": "md-original", "width": 800, "format": "original"},
        {"name": "lg-original", "width": 1600, "format": "original"},
    ],
)

MEDIA_RENDITIONS_FOLDER = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.FOLDER", "renditions"
)

MEDIA_RENDITIONS_JPEG_QUALITY = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.JPEG_QUALITY", 85
)

MEDIA_RENDITIONS_WEBP_QUALITY = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.WEBP_QUALITY", 82
)

MEDIA_RENDITIONS_AVIF_QUALITY = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.AVIF_QUALITY", 60
)

MEDIA_RENDITIONS_PREVENT_INFLATE = pointed_getter(
    django_settings, "CAMOMILLA.MEDIA.RENDITIONS.PREVENT_INFLATE", True
)

API_NESTING_DEPTH = pointed_getter(django_settings, "CAMOMILLA.API.NESTING_DEPTH", 10)

# Auth-user columns that ``SafeNestingMixin`` strips when a depth-based read
# serializer auto-nests a FK to ``AUTH_USER_MODEL`` (e.g. an article ``author``
# on the public, unauthenticated page router). Everything *not* listed here —
# including a project's own custom user columns — is exposed automatically;
# only these known-sensitive defaults are removed. Add your custom user model's
# secret columns here to keep them out of public nested output.
SAFE_NESTING_SENSITIVE_USER_FIELDS = pointed_getter(
    django_settings,
    "CAMOMILLA.API.SAFE_NESTING.SENSITIVE_USER_FIELDS",
    (
        "password",
        "last_login",
        "is_superuser",
        "is_staff",
        "is_active",
        "email",
        "groups",
        "user_permissions",
    ),
)

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

PAGE_ROUTER_CACHE = pointed_getter(
    django_settings, "CAMOMILLA.API.PAGES.ROUTER_CACHE", 60 * 15
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
#         "THUMBNAIL": {"FOLDER": "", "WIDTH": 50, "HEIGHT": 50},
#         "RENDITIONS": {
#             "ENABLE": True,
#             "FOLDER": "renditions",
#             "VARIANTS": [
#                 {"name": "sm-webp", "width": 400, "format": "webp"},
#                 {"name": "md-webp", "width": 800, "format": "webp"},
#                 {"name": "lg-webp", "width": 1600, "format": "webp"},
#                 {"name": "sm-avif", "width": 400, "format": "avif"},
#                 {"name": "md-avif", "width": 800, "format": "avif"},
#                 {"name": "lg-avif", "width": 1600, "format": "avif"},
#                 {"name": "sm-original", "width": 400, "format": "original"},
#                 {"name": "md-original", "width": 800, "format": "original"},
#                 {"name": "lg-original", "width": 1600, "format": "original"},
#             ],
#             "JPEG_QUALITY": 85,
#             "WEBP_QUALITY": 82,
#             "AVIF_QUALITY": 60,
#             "PREVENT_INFLATE": True,
#         },
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
#     "API": {
#         "NESTING_DEPTH": 10,
#         "TRANSLATION_ACCESSOR": "translations",
#         "PAGES": {
#             "DEFAULT_SERIALIZER": "camomilla.serializers.page.RouteSerializer"
#         },
#         "ROUTER_CACHE": 60 * 15,
#         # Blacklist (fail-open): when a FK to AUTH_USER_MODEL is auto-nested
#         # in API output, these columns are stripped and everything else —
#         # including your custom user columns — is exposed. Add any secret
#         # columns of a custom user model here.
#         "SAFE_NESTING": {
#             "SENSITIVE_USER_FIELDS": (
#                 "password", "last_login", "is_superuser", "is_staff",
#                 "is_active", "email", "groups", "user_permissions",
#             )
#         }
#     },
#     "DEBUG": False
# }
