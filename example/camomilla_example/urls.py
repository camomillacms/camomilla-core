"""
URL configuration for camomilla_example project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path, re_path
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as staticserve
from django.contrib.sitemaps.views import sitemap
from camomilla.sitemap import camomilla_sitemaps


urlpatterns = [
    path("tinymce/", include("tinymce.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("api/camomilla/", include("camomilla.urls")),
    path("api/models/", include("camomilla.model_api")),
    path("", include("structured.urls")),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": camomilla_sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
]


if getattr(settings, "DEBUG", False) or getattr(settings, "DEBUG404", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            staticserve,
            {"document_root": settings.STATIC_ROOT},
        )
    ]

urlpatterns += i18n_patterns(
    path("", include("camomilla.dynamic_pages_urls")), prefix_default_language=False
)

if settings.ENABLE_DEBUG_TOOLBAR:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns = debug_toolbar_urls() + urlpatterns
