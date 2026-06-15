---
name: camomilla-usage
description: >-
  Use when building a Django project ON TOP OF camomilla (consuming
  django-camomilla-cms as a dependency): installation and INSTALLED_APPS/URL
  wiring, the REST API surface and authentication, adding custom pages, the
  page lifecycle / drafts / preview / scheduling, media, menus, translations,
  Meta models, StructuredJSONField and the typed Permalink link, settings.
  NOT for editing camomilla's own source code — use the
  camomilla-internal-architecture skill for that.
---

# Camomilla CMS — Usage Skill

> Django-based headless CMS providing REST APIs, media management, multilingual support, and a flexible page system. This skill is for using camomilla as a library in your Django project.

**When to use this skill vs. the other:** Use **camomilla-usage** when you're writing code in your *own* app (`myapp/`) that depends on camomilla — wiring settings, calling its API, subclassing `AbstractPage`. Use **camomilla-internal-architecture** when you're editing files *inside* the `camomilla/` package itself (its models, serializers, views, managers, tests). Rule of thumb: editing `camomilla/...` → internal-architecture; editing `myapp/...` → usage.

## Stack and versions

| Dependency | Version |
|---|---|
| Python | >= 3.10, < 3.15 |
| Django | >= 4.2, <= 5.2 |
| django-camomilla-cms | >= 6.0.0 |

Camomilla pulls these in as **hard** dependencies (all installed automatically, all required): `djangorestframework`, `django-modeltranslation`, `Pillow`, `pydantic`, `django-structured-json-field`, `django-structured-metaobjects` (powers the Meta-models API), `django-reversion` (powers page revisions), `django-admin-interface`, `django-ckeditor`, `django-tinymce`, `djsuperadmin`, `python-magic`, `django_jsonform`, `inflection`, `uritemplate`. See `pyproject.toml` for the authoritative list.

> Note: `django-reversion` ships by default, so the `/revisions/` and `/revert/` endpoints work out of the box. They only degrade to `501 Not Implemented` if you deliberately remove `reversion` from `INSTALLED_APPS`. Two of these deps are Django apps you must list in `INSTALLED_APPS` yourself — `structured_metaobjects` and `reversion` (see below).

## Initial setup

### 1. Installation

```bash
pip install django-camomilla-cms>=6.0.0
```

### 2. INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'modeltranslation',          # BEFORE django.contrib.admin if using translations
    'django.contrib.admin',
    ...
    'camomilla',                 # always required
    'camomilla.theme',           # to customize the admin interface
    'structured_metaobjects',    # REQUIRED — camomilla.urls imports it unconditionally
    'reversion',                 # page revisions (/revisions/, /revert/); ships by default
    'djsuperadmin',              # optional, for inline content editing
    'rest_framework',            # always required
    'rest_framework.authtoken',  # always required
    ...
    'myapp',                     # your app
]
```

> `structured_metaobjects` is **not optional**: `camomilla/urls.py` imports `structured_metaobjects.views` at module load, so `include('camomilla.urls')` raises `ImportError` if the app isn't installed. Run `manage.py migrate` after adding it.

### 3. Camomilla migrations folder

Create a dedicated folder for camomilla migrations (they can't live in the installed package):

```bash
mkdir -p camomilla_migrations
touch camomilla_migrations/__init__.py
```

In `settings.py`:

```python
MIGRATION_MODULES = {"camomilla": "camomilla_migrations"}
```

### 4. URL configuration

```python
# <project>/urls.py
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/camomilla/', include('camomilla.urls')),       # Built-in API endpoints
    path('api/models/', include('camomilla.model_api')),     # API for models registered with @model_api.register()
    path('', include('camomilla.dynamic_pages_urls')),       # MUST be LAST
]
```

For multilingual sites:

```python
from django.conf.urls.i18n import i18n_patterns

urlpatterns += i18n_patterns(
    path('', include('camomilla.dynamic_pages_urls')),
    prefix_default_language=False,
)
```

### 5. Migrations

```bash
python manage.py makemigrations camomilla
python manage.py migrate
```

## Architecture — what camomilla provides

### Built-in API endpoints

| Endpoint | Purpose |
|---|---|
| `/api/camomilla/pages/` | Pages CRUD |
| `/api/camomilla/pages-router/<permalink>` | Page lookup by URL (cached) |
| `/api/camomilla/articles/` | Articles CRUD |
| `/api/camomilla/tags/` | Tags CRUD |
| `/api/camomilla/contents/` | Content blocks CRUD |
| `/api/camomilla/media/` | Media CRUD (multipart upload) |
| `/api/camomilla/media-folders/` | Media folder navigation |
| `/api/camomilla/menus/` | Menus CRUD |
| `/api/camomilla/meta-types/` | MetaType definitions CRUD |
| `/api/camomilla/meta-instances/` | MetaInstance data CRUD |
| `/api/camomilla/meta-instances/schema/?meta_type=<id>` | JSON Schema for a given MetaType |
| `/api/camomilla/users/` | User management |
| `/api/camomilla/languages/` | Available languages |
| `/api/camomilla/token-auth/` | Token authentication |

### Common query parameters for all endpoints

| Param | Example | Description |
|---|---|---|
| `items` | `?items=10` | Enable pagination, items per page |
| `page` | `?page=2` | Page number |
| `sort` | `?sort=-created,title` | Ordering (- for desc) |
| `search` | `?search=term` | Full-text search |
| `fields` | `?fields=id,title` | Limit returned fields |
| `language` | `?language=it` | Switch response language |
| `fltr` | `?fltr=published_at__isnull=False` | Filter with Django syntax (operates on real columns — `status` is derived, not filterable here; use endpoint-specific helpers like `/public` or queryset methods server-side for lifecycle state) |

### Pagination format

Without `?items`: simple array `[{...}, {...}]`

With `?items=10`:
```json
{
    "items": [{...}, {...}],
    "paginator": {
        "count": 42,
        "page": 1,
        "has_next": true,
        "has_previous": false,
        "pages": 5,
        "page_size": 10
    }
}
```

### API translation format

Input (POST/PATCH):
```json
{"translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}}
```
Or flat: `{"title_en": "Hello", "title_it": "Ciao"}`

Output (GET):
```json
{
    "title": "Hello",
    "translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}
}
```

Use `?included_translations=all` or `?included_translations=en,it` to control which translations to include.

### Authentication

The API ships with this DRF default (set it in your project's `REST_FRAMEWORK` setting):

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "camomilla.authentication.SessionAuthentication",   # camomilla's variant DOES return 401 (the DRF default returns 403)
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly",
    ],
}
```

**Default permission posture:** anonymous users get **read-only** access; writes require the matching Django **model permission** (`add`/`change`/`delete`). Page lifecycle actions use the stricter `CamomillaBasePermissions` (see "Page viewset actions").

**Two ways to authenticate** (both work everywhere; pick per client):

| Method | How | Use for |
|---|---|---|
| **Token** | `POST /api/camomilla/token-auth/` with `{"username","password"}` → `{"token": "…"}`; then send `Authorization: Token <token>` on every request. | Headless frontends, scripts, the preview endpoints. |
| **Session** | `POST /api/camomilla/auth/login/` (sets the session cookie); `POST /api/camomilla/auth/logout/`. | Browser/admin-adjacent UIs already holding a session. |

A headless editor frontend hitting `pages-router-preview` or the by-id lifecycle actions sends the `Authorization: Token …` header obtained from `token-auth/`.

## How to add a custom page

This is the most common task. Follow all steps.

### Step 1 — Model

```python
# myapp/models.py
from django.db import models
from camomilla.models import AbstractPage

class ProductPage(AbstractPage):
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=100, unique=True)
    image = models.ForeignKey(
        "camomilla.Media", blank=True, null=True,
        on_delete=models.SET_NULL, related_name="product_images",
    )

    class Meta:
        verbose_name = "Product Page"
        verbose_name_plural = "Product Pages"

    class PageMeta:
        parent_page_field = "parent_page"  # default, change if you have a different FK
        default_template = "website/product.html"
        standard_serializer = "myapp.serializers.ProductPageSerializer"

    def __str__(self):
        return self.title
```

`AbstractPage` already includes: `title`, `description`, SEO fields (og_*, canonical, keywords), `template`, `template_data` (JSONField), `ordering`, `parent_page`, `identifier` (UUID), `published_at` (translatable, when this language went/goes public), `deleted_at` (global soft-delete marker), `autopermalink`, `breadcrumbs_title`.

**Lifecycle labels (derived, not stored as a column):** `PUB` (Published), `DRF` (Draft), `TRS` (Trashed), `PLA` (Planned). `status`, `is_public`, `has_draft`, `has_scheduled_draft` are read-only Python properties. The label is computed at read time from `published_at` + `deleted_at` + the `Draft` table; there is no `status` column to set. Filtering: `Page.objects.filter(status="PUB")` / `.exclude(status="TRS")` / `.filter(is_public=True)` work — the manager rewrites those lookups into the equivalent timestamp conditions. `Page.objects.public()` / `.trashed()` / `.draft()` / `.scheduled()` are the explicit canonical helpers; for `order_by` / `values("status")` use `.with_lifecycle()` (annotates `computed_status`).

### Step 2 — Translation registration

```python
# myapp/translation.py
from modeltranslation.translator import translator
from camomilla.translation import AbstractPageTranslationOptions
from .models import ProductPage

class ProductPageTranslationOptions(AbstractPageTranslationOptions):
    fields = ()  # add custom translatable fields here

translator.register(ProductPage, ProductPageTranslationOptions)
```

`AbstractPageTranslationOptions` already includes translation for: title, description, og_*, canonical, keywords, breadcrumbs_title, autopermalink, indexable, template_data, `published_at`. The `deleted_at` field is global (not translated) so trashing affects all languages at once; to dismiss a single language without affecting the others, clear that language's `published_at` (see "Page lifecycle and drafts" below).

### Step 3 — Serializer

```python
# myapp/serializers.py
from camomilla.serializers.base import BaseModelSerializer
from camomilla.serializers.mixins import AbstractPageMixin
from .models import ProductPage

class ProductPageSerializer(AbstractPageMixin, BaseModelSerializer):
    class Meta:
        model = ProductPage
        fields = "__all__"
```

**Important:** for page models, ALWAYS use `AbstractPageMixin` + `BaseModelSerializer`. `AbstractPageMixin` adds: permalink validation, breadcrumbs, routerlink, alternate URLs.

### Step 4 — Admin

```python
# myapp/admin.py
from django.contrib import admin
from camomilla.theme.admin.pages import AbstractPageAdmin, AbstractPageModelForm
from .models import ProductPage

class ProductPageForm(AbstractPageModelForm):
    class Meta:
        model = ProductPage
        fields = "__all__"

class ProductPageAdmin(AbstractPageAdmin):
    form = ProductPageForm

admin.site.register(ProductPage, ProductPageAdmin)
```

### Step 5 — Migrations

```bash
python manage.py makemigrations myapp
python manage.py migrate
```

The page is now accessible via:
- Django Admin
- API: `/api/camomilla/pages-router/<permalink>`
- Template rendering: visit the permalink in the browser

## Page lifecycle and drafts

Camomilla pages have a derived lifecycle and a dedicated `Draft` table for pending edits and scheduled content swaps. There is no `status` column — the label is a function of two timestamps + the Draft table.

### Lifecycle model

| State | When |
|---|---|
| `PUB` Published | `deleted_at IS NULL AND published_at <= now()` (active language) |
| `DRF` Draft | `deleted_at IS NULL AND published_at IS NULL` |
| `PLA` Planned | `deleted_at IS NULL AND published_at > now()` (legacy "scheduled first publish") |
| `TRS` Trashed | `deleted_at IS NOT NULL` (global) |

`Draft` rows sit alongside the page row: they hold a partial-PATCH-shaped payload for the next edit. The presence of a Draft does not affect the lifecycle label — observe drafts via `page.has_draft` / `page.has_scheduled_draft` / `Page.objects.draft()`.

### Public route safety

Both the HTML render route (`dynamic_pages_urls`) and the JSON router (`/api/camomilla/pages-router/<permalink>`) gate every response on `is_public` after a single lazy-publish attempt. Trashed, draft, and scheduled-first-publish rows return 404. Only authenticated authors can see non-public state, via the preview surfaces below.

### Preview surfaces

Three authenticated ways to look at unpublished content. They all **overlay the active-language pending draft** on top of the live row, and — unlike the public routes — do **not** run lazy-publish (looking at a preview must not consume a scheduled draft as a side effect). Auth differs slightly: the by-id viewset actions use `CamomillaBasePermissions` (GET = any authenticated user; writes need the matching Django model perm; superusers bypass); the by-URL `pages-router-preview` requires authentication (`IsAuthenticated`).

| Endpoint | Routed by | Returns | Use it for |
|---|---|---|---|
| `GET /api/camomilla/pages-router-preview/<page_url>` | **URL** (mirror of `pages-router`) | JSON, same shape as `pages-router` + `has_draft` | **Headless frontends** (Astro, custom JS): resolve a page to preview by its URL in a single request — no list-then-detail round trip. |
| `GET /api/camomilla/pages/{id}/preview/` | id | JSON: live page + draft overlay | Admin Draft Inspector / anything that already has the page id. |
| `GET /api/camomilla/pages/{id}/render/` | id | HTML: page template rendered with `draft_data` in context | Server-rendered preview of the actual template. |

`pages-router-preview` is the headless counterpart of `pages-router`: identical payload, but it bypasses the `is_public` gate (so trashed / draft / scheduled rows return their content), attaches `has_draft: true` when a draft exists, and applies the same canonical-URL redirect descriptors. A typical frontend calls `pages-router` normally and switches to `pages-router-preview` (with the editor's auth) only when a `?preview=…` flag is present.

### Page viewset actions

All gated by `CamomillaBasePermissions`: the read action (`revisions`) needs an authenticated user; the write actions (draft/publish/schedule/discard-draft/revert) need the matching Django model permission (`add`/`change`/`delete`) on the page model; superusers bypass. (Not "staff" — `is_staff` is never checked.)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/camomilla/pages/{id}/draft/` | `PATCH` / `PUT` | Save the active-language draft. `PATCH` merges into the existing payload; `PUT` replaces wholesale. |
| `/api/camomilla/pages/{id}/discard-draft/` | `POST` | Delete the active-language Draft row. |
| `/api/camomilla/pages/{id}/publish/` | `POST` | Apply the active-language draft (if any) and stamp `published_at = now()`. Body may include `comment` (reversion). |
| `/api/camomilla/pages/{id}/schedule/` | `POST` | Body `{"publish_at": "<ISO 8601>"}`. Never-public language → sets `published_at` to that moment. Already-public language → attaches `scheduled_for` to the existing Draft (call `/draft/` first). |
| `/api/camomilla/pages/{id}/preview/` | `GET` | Author-only JSON: live page + draft overlay merged by language. |
| `/api/camomilla/pages/{id}/render/` | `GET` | Author-only HTML: render the page template with `draft_data` in the template context. |
| `/api/camomilla/pages/{id}/revisions/` | `GET` | List `django-reversion` Version snapshots (returns 501 if reversion not installed). |
| `/api/camomilla/pages/{id}/revert/{version_id}/` | `POST` | Revert to a Version (creates a new reversion entry). |

### Lazy materialization

If a Draft's `scheduled_for` is in the past, the first public reader of that page (HTML or JSON router) applies it and serves the new content — concurrent-safe, no background worker required. The cron command below is the safety net for pages nobody visits. (Locking/concurrency internals are documented in the camomilla-internal-architecture skill.)

### Cron command — `camomilla_publish_scheduled`

```bash
python manage.py camomilla_publish_scheduled
```

Walks `camomilla.preview.resolve_scheduled_pages()` (which yields each due `(page, language)` from `Draft.objects.due_now()`) and publishes each. Schedule it via cron / Celery beat / similar. Idempotent and safe to run frequently.

### QuerySet helpers (`Page.objects`)

```python
Page.objects.public()                # deleted_at IS NULL AND published_at <= now()
Page.objects.alive()                 # deleted_at IS NULL
Page.objects.trashed()               # deleted_at IS NOT NULL
Page.objects.draft()                 # has any pending Draft (any language)
Page.objects.scheduled()             # has scheduled Draft OR published_at > now()
Page.objects.due_for_publish()       # has Draft with scheduled_for <= now()
Page.objects.first_publish_pending() # never-public with future published_at
Page.objects.with_lifecycle()        # annotates computed_status for ORDER BY / .values()
```

All helpers respect the active language for `published_at`.

### Per-language dismiss (404 only one language)

`published_at` is translatable; clearing one language's column 404s that language without affecting the others. `deleted_at` is global by design — trashing kills every language.

```python
from camomilla.utils import set_nofallbacks

# 404 English, keep Italian / others live
set_nofallbacks(page, "published_at", None, language="en")
page.save()

# Or via direct ORM (skips save() side effects):
Page.objects.filter(pk=page.pk).update(published_at_en=None)
```

### Programmatic API

```python
page.save_draft({"translations": {"en": {"title": "edited"}}})  # active language
page.save_draft({"title": "edited"}, scheduled_for=when)        # schedule the swap
page.discard_draft()                                            # delete the Draft row
page.publish(comment="Editor approved")                          # apply draft + mark live
page.schedule(when)                                             # see PageMeta semantics
page.trash()                                                    # soft-delete (global)
page.restore()                                                  # undo trash
page.list_revisions()                                           # reversion history
page.revert_to_revision(version_id)                             # rollback
```

### Optional `django-reversion` integration

If installed, `publish()`, `publish_if_due()`, and `revert_to_revision()` create reversion `Revision` entries. The `/revisions/` and `/revert/` endpoints return `501 Not Implemented` when reversion is absent. Add it to `INSTALLED_APPS` and run migrations to enable.

### Upgrading an existing project (status → lifecycle)

Projects upgrading from camomilla ≤ 6.4 have data in the old `status` (translatable CharField PUB/DRF/PLA/TRS) + `publication_date` columns; the new system derives state from `published_at` + `deleted_at`. **Recommended path:** run `python manage.py camomilla_makemigrations` (a drop-in `makemigrations` wrapper, no app arg — covers camomilla's models AND custom `AbstractPage` subclasses in your own apps) — it detects the transition and auto-inserts **one `MigrateStatusToLifecycle("<model>")` per page model** into each generated migration (each op migrates only its own model, so per-app migrations never overlap), so you just `migrate`, no hand-editing. Under the hood it injects the custom operation `camomilla.upgrades.MigrateStatusToLifecycle("<model>")` — one per page model, each migrating only its own model (also droppable into a plain `makemigrations` output by hand). The transform maps every page model per-language (PUB→past published_at; PLA→publication_date; DRF/TRS→null; global `deleted_at` only when all languages are TRS), preserving the old `is_public` result exactly. Drafts start empty (the old system had no draft storage). Full procedure: the "Upgrading from status-based publication" docs page.

## How to create an API endpoint for a model

### Option A: `@model_api.register()` decorator (quick)

```python
# myapp/models.py
from django.db import models
from camomilla import model_api

@model_api.register()
class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

This automatically creates `/api/models/product/` with full CRUD, pagination, search, and filters.

To customize:

```python
@model_api.register(
    serializer_meta={"fields": ["id", "name", "price"], "depth": 2},
    viewset_attrs={"search_fields": ["name"]},
    filters={"is_active": True},  # pre-filter the queryset
)
class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
```

**URL prerequisite:** `path('api/models/', include('camomilla.model_api'))` in your `urls.py`.

### Option B: manual serializer + viewset (full control)

```python
# myapp/serializers.py
from camomilla.serializers.base import BaseModelSerializer
from .models import Product

class ProductSerializer(BaseModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
        depth = 5  # relation nesting depth (default from settings)
```

```python
# myapp/views.py
from camomilla.views.base import BaseModelViewset
from camomilla.permissions import CamomillaBasePermissions
from .models import Product
from .serializers import ProductSerializer

class ProductViewSet(BaseModelViewset):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (CamomillaBasePermissions,)
    model = Product
    search_fields = ["name", "description"]
```

```python
# myapp/urls.py
from rest_framework import routers
from .views import ProductViewSet

router = routers.DefaultRouter()
router.register("products", ProductViewSet, "product")
urlpatterns = router.urls
```

**Always use `BaseModelSerializer` and `BaseModelViewset`.** They provide: nested translations, auto-nesting relations, pagination, search, filters, query optimization, partial PATCH on JSONField.

### Additional viewset features

**Action-specific serializers:**

```python
class ProductViewSet(BaseModelViewset):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    action_serializers = {
        "list": ProductListSerializer,      # lighter for lists
        "retrieve": ProductDetailSerializer,  # more detailed
    }
```

**Custom eager loading:**

```python
class ProductSerializer(BaseModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"

    @classmethod
    def setup_eager_loading(cls, queryset, context=None):
        return queryset.select_related("category").prefetch_related("tags")
```

**Bulk delete:**

```python
from camomilla.views.mixins import BulkDeleteMixin

class ProductViewSet(BulkDeleteMixin, BaseModelViewset):
    # Adds DELETE /products/ with body {"ids": [1,2,3]}
    ...
```

## How to use media

### Attach media to a model

```python
class MyModel(models.Model):
    image = models.ForeignKey(
        "camomilla.Media", blank=True, null=True,
        on_delete=models.SET_NULL,
    )
    gallery = models.ManyToManyField("camomilla.Media", blank=True)
```

### Upload via API

`POST /api/camomilla/media/` with `Content-Type: multipart/form-data`

Payload: `file` (the file), `title`, `alt_text`, `description`, `folder` (ID).

Images are automatically optimized (resize, DPI) and a thumbnail is generated.

### Optimization configuration

```python
CAMOMILLA = {
    "MEDIA": {
        "OPTIMIZE": {
            "MAX_WIDTH": 1980,
            "MAX_HEIGHT": 1400,
            "DPI": 30,
            "JPEG_QUALITY": 85,
            "ENABLE": True,
        },
        "THUMBNAIL": {"FOLDER": "", "WIDTH": 50, "HEIGHT": 50},
    },
}
```

## How to use menus

### In templates

```html
{% load menus %}
<header>
    {% render_menu "main_menu" %}
</header>
```

The `render_menu` tag creates or fetches the menu from DB and renders it. Pass a second argument for a custom template:

```html
{% render_menu "main_menu" "website/parts/menu.html" %}
```

Menus are managed from the admin. The structure is tree-based (nodes with sub-nodes).

### Node links

Each node's `link` is a [`camomilla.types.Permalink`](#typed-template_data-on-a-page-model) — the same polymorphic link primitive used in typed `template_data`. A link is either **relational** (a `UrlNode` FK to a camomilla page, survives renames, resolves per-language) or **static** (a free-form URL string for externals / `mailto:` / anchors).

Resolve a node to a URL in a custom menu template with the `node_url` filter — not by reading `link.url` directly — so both link kinds work, and pass `request` to get an **absolute** URL:

```html
{% load menus %}
{{ item|node_url }}          {# root-relative, e.g. /it/about/ #}
{{ item|node_url:request }}  {# absolute, e.g. https://host/it/about/ #}
```

`request` is always safe to pass: the menu renderer binds it into the template context (falling back to `None`), and static links ignore it.

## How to inject context into pages

### Recommended method: `template_context.py`

Create a `template_context.py` file in your app. Camomilla auto-discovers it.

**By template:**

```python
# myapp/template_context.py
from camomilla.templates_context.rendering import register
from camomilla.models import Media

@register("website/home.html")
def home_page(request, super_ctx):
    return {
        "featured_media": Media.objects.all()[:5],
    }
```

**By page model:**

```python
from camomilla.templates_context.rendering import register
from .models import ProductPage

@register(page_model=ProductPage)
def product_context(request, super_ctx):
    page = super_ctx.get("page")
    return {
        "related_products": ProductPage.objects.public()
            .exclude(pk=page.pk)[:4],
    }
```

The `request` and `super_ctx` kwargs are optional in the signature.

### Alternative method: PageMeta.inject_context_func

```python
class MyPage(AbstractPage):
    class PageMeta:
        def inject_context_func(request, super_ctx):
            return {"extra_data": "value"}
```

## How to use Meta models

Meta models allow editors to define new data types dynamically via the admin — no code changes needed. A **MetaType** declares a list of fields (with name, type, optional/required, translated, nested children). A **MetaInstance** holds a concrete entry whose shape is validated against its MetaType at save time.

### When to use

- You need content types that editors can define and evolve without developer involvement (FAQs, team members, testimonials, product specs, etc.)
- You want a typed, validated JSON payload per content type without writing a new Django model for each one.

### Built-in field kinds

The `kind` must be one of the `MetaFieldKind` values below — these are the **only** accepted kinds; anything else fails Pydantic validation on save. Each kind unlocks specific extra options on the field definition.

| Kind | Python type | Per-kind options | Notes |
|---|---|---|---|
| `string` | `str` | `multiline`, `placeholder`, `min_length`, `max_length` | Single- or multi-line (`multiline: true`) text. There is **no** `text` kind. |
| `html` | `str` | `placeholder` | Rich-text / HTML body |
| `number` | `float` \| `int` | `integer`, `minimum`, `maximum` | Set `integer: true` for an int. There is **no** separate `integer` kind. |
| `boolean` | `bool` | — | |
| `date` | `date` | — | |
| `datetime` | `datetime` | — | |
| `select` | `str` | `choices` | Enumerated value; `choices` is a list of `{value, label}` |
| `ref` | any Django model | `target_model` | FK; stores PK, returns instance. A **media** field is `ref` with `target_model: "camomilla.Media"` — there is no `media` kind. |
| `queryset` | list of a Django model | `target_model` | M2M-like ordered list of PKs |
| `group` | nested object | `children` | Recursive list of field defs |
| `list` | list of objects | `children` | Recursive list of field defs |

### Creating a MetaType via admin

1. Go to **Admin → Meta types → Add**.
2. Fill in `key` (slug, unique) and `name`.
3. In the **Schema** structured editor, add field rows. Each row has:
   - `name` — Python/JSON key
   - `label` — human-readable label
   - `kind` — field type (see table above)
   - `required` / `translated` toggles
   - `target_model` — visible only when `kind = ref`; select from the dropdown of all installed models
   - `children` — visible only when `kind = group` or `list`; recursive list of field defs

### Creating a MetaType via API

```http
POST /api/camomilla/meta-types/
Content-Type: application/json

{
    "key": "faq",
    "name": "FAQ",
    "schema": [
        {"name": "question", "kind": "string", "required": true, "translated": true},
        {"name": "answer",   "kind": "text",   "required": true, "translated": true},
        {"name": "weight",   "kind": "integer"}
    ]
}
```

### Creating a MetaInstance via API

```http
POST /api/camomilla/meta-instances/
Content-Type: application/json

{
    "meta_type": 1,
    "identifier": "faq-001",
    "data": {
        "question": {"en": "What is camomilla?", "it": "Cos'è camomilla?"},
        "answer":   {"en": "A headless CMS.",    "it": "Un CMS headless."},
        "weight": 10
    }
}
```

The `data` payload is validated server-side against the MetaType schema. Missing required fields or wrong types return a `400` with field-level errors.

### Fetching the JSON Schema for a MetaType

Frontends can request the JSON Schema for any MetaType to drive dynamic form rendering:

```http
GET /api/camomilla/meta-instances/schema/?meta_type=1
```

Returns a standard JSON Schema object. The per-type schema is also exposed on the MetaType resource itself:

```http
GET /api/camomilla/meta-types/1/schema/
```

### Nested group and list fields

```http
POST /api/camomilla/meta-types/
{
    "key": "product-spec",
    "name": "Product Spec",
    "schema": [
        {"name": "title", "kind": "string", "required": true},
        {
            "name": "attributes",
            "kind": "list",
            "children": [
                {"name": "label", "kind": "string", "required": true},
                {"name": "value", "kind": "string"}
            ]
        },
        {
            "name": "dimensions",
            "kind": "group",
            "children": [
                {"name": "width",  "kind": "number"},
                {"name": "height", "kind": "number"},
                {"name": "depth",  "kind": "number"}
            ]
        }
    ]
}
```

### Translated fields

Setting `"translated": true` on a field wraps its value in a `{"en": ..., "it": ...}` language-keyed object, consistent with the rest of Camomilla's translation format.

### Referencing another Django model

```json
{
    "name": "author",
    "kind": "ref",
    "target_model": "auth.User",
    "required": true
}
```

In the admin, `target_model` renders as a select populated with every installed model in `app.ModelName` format. The stored value is the referenced instance's PK, serialized back as the full object representation.

### Schema cache

The runtime Pydantic model built from a MetaType is cached per `(meta_type_id, compiled_at)`. Saving a MetaType (admin or API) invalidates the cache automatically — all subsequent requests use the new schema immediately.

## How to use StructuredJSONField

For typed JSON data with Pydantic validation.

### Define a schema

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField
from structured.pydantic.fields import QuerySet
from django.contrib.auth.models import User

class HeroSchema(BaseModel):
    title: str
    subtitle: str = ""
    cta_url: str = ""
    background: "camomilla.Media" = None     # FK - stores PK, returns instance
    featured_items: QuerySet["myapp.Product"]  # M2M-like - stores PK list, returns queryset

class HomePage(AbstractPage):
    hero = StructuredJSONField(schema=HeroSchema, default=dict)
```

### Key features

- **Validation:** Pydantic validates on save. Non-conforming JSON raises `ValidationError`
- **FK in JSON:** declaring a field with a Django Model type stores only the PK but returns the instance
- **QuerySet in JSON:** `QuerySet[Model]` stores an ordered list of PKs, returns a Django queryset preserving order
- **Recursive nesting:** use string type hints: `child: "MySchema"`
- **List:** use `default=list` to accept an array of objects
- **Built-in cache:** minimizes DB queries for FK/QuerySet. Can be disabled in settings

```python
CAMOMILLA = {
    "STRUCTURED_FIELD": {"CACHE_ENABLED": True}  # default
}
```

### Typed `template_data` on a page model

The supported pattern for richer page editing: redeclare `template_data` on your concrete `AbstractPage` subclass with a typed schema. The editor gets a structured form, the API gets validated payloads, and URL-bearing fields get per-language routerlinks for free via `camomilla.types.Permalink` — the same polymorphic link primitive that powers `MenuNode.link`.

```python
# myapp/models.py
from typing import List, Optional
from camomilla.models import AbstractPage
from camomilla.types import Permalink
from structured.fields import StructuredJSONField
from structured.pydantic.models import BaseModel


class HeroBlock(BaseModel):
    headline: str = ""
    subheadline: str = ""
    cta_label: str = ""
    # ``Permalink`` is a polymorphic struct. ``link_type=RE`` holds a FK
    # to a ``UrlNode`` (the editor picks a real page); ``link_type=ST``
    # holds a free-form URL string (externals, ``mailto:``, anchors).
    # Either way, ``.url`` is the language-aware output URL — for a
    # relational link via ``UrlNode.routerlink``, for a static link
    # verbatim. Frontends should bind ``href`` to ``cta.url``.
    cta: Optional[Permalink] = None


class FeatureBlock(BaseModel):
    icon: str = ""
    title: str = ""
    description: str = ""


class HomePageData(BaseModel):
    hero: HeroBlock = HeroBlock()
    features: List[FeatureBlock] = []


def _home_default():
    return HomePageData()


class HomePage(AbstractPage):
    template_data = StructuredJSONField(schema=HomePageData, default=_home_default)

    class PageMeta:
        default_template = "website/pages/home.html"
```

```python
# myapp/translation.py
# Required so each lang gets its own ``template_data_<lang>`` column
# (otherwise modeltranslation falls back to the single base column and
# different locales overwrite each other on save).
from modeltranslation.translator import register
from camomilla.translation import AbstractPageTranslationOptions
from .models import HomePage


@register(HomePage)
class HomePageTranslationOptions(AbstractPageTranslationOptions):
    pass
```

Then `python manage.py makemigrations myapp` materialises both the base `template_data` column and the per-language `template_data_en` / `template_data_it` columns, all of type `StructuredJSONField` with the same schema.

#### Why `Permalink` instead of a bare string

Editors used to stash URLs in JSON as raw permalinks like `"/about"`. A Django template could resolve that with `{% localized_url … %}`, but a JS frontend (Astro, a mobile app) had no way to know the string was a camomilla permalink that needed an i18n prefix. Typing the field as `Permalink` fixes both sides at the data layer:

- **Storage** holds the editor's choice as either `{link_type: "RE", url_node: <PK>}` or `{link_type: "ST", static: "<url>"}`. Renames don't break the link — the FK tracks the row, not the URL string. Deleting the target nulls the FK rather than silently breaking the string.
- **Output** carries a derived `url` field (`computed_field`) that's already localized: `UrlNode.routerlink` honours `i18n_patterns` + `APPEND_SLASH`, so the same struct emits `"/about/"` on EN and `"/it/about/"` on IT without any consumer-side work.
- **No round-trip corruption.** `url` is derived, not persisted. Writing the response back as-is just re-stores the same struct.

The same shape is used by `MenuNode.link` — one editor pattern, one resolver, one type.

#### Editor experience

The admin form generated from the schema renders a discriminator (radio between "internal page" and "external URL") and conditional fields driven by `model_config.json_schema_extra` — `static` shows for `ST`, `url_node` shows for `RE`, and the derived `page` / `content_type` are hidden. This is the same UX the menu editor has used for years.

#### Constructing a `Permalink` in code

In fixtures / migrations / tests where you need to build one by hand:

```python
from camomilla.types import LinkTypes, Permalink

# Relational — to a camomilla page
cta = Permalink(link_type=LinkTypes.relational, url_node=about_page.url_node)

# Static — for an external target
cta = Permalink(link_type=LinkTypes.static, static="https://example.com")
```

The model-level validator (`_derive_page_and_content_type`) backfills `page` / `content_type` from `url_node` after construction, so you only need to pass the `UrlNode`.

#### Rendering on the server side

Django templates can dereference the computed URL directly — no template tag needed:

```django
{% if page.template_data.hero.cta %}
  <a href="{{ page.template_data.hero.cta.url }}">{{ page.template_data.hero.cta_label }}</a>
{% endif %}
```

The same JSON shape ships through the `pages-router` API, so a JS frontend reads `data.template_data.hero.cta.url` and binds it to `href` without any additional logic.

**Relative vs absolute.** The `url` computed field is always **root-relative** (`/it/about/`) — a pydantic computed field can't reach the serialization context, so there's no request to build an absolute URI from. That's the right default for a headless API whose host may differ from the frontend's. When you need an absolute link (sitemaps, emails, server-rendered templates), call `get_url(request)` instead of reading `.url`:

```python
link.url                   # "/it/about/"               (root-relative)
link.get_url(request=req)  # "https://host/it/about/"   (absolute)
```

The same threading exists on `UrlNode` (`get_routerlink(request)` vs the `routerlink` property) and in templates: the `localized_url` tag and the `node_url:request` filter return absolute URLs when a request is in context.

#### When `Permalink` is not the right field

| Use `Permalink` | Use plain `str` |
| --- | --- |
| Editor picks a page from a dropdown | Free-form rich text |
| Internal navigation targets that should track renames | Anchors (`#section`) the editor knows ahead of time |
| Mixed internal + external links in the same field | An ID, a slug, or any non-URL string that just happens to look URL-ish |

Static URLs *are* supported by `Permalink` (`link_type=ST`), so a single field can hold either internal or external — the discriminator is what tells consumers how to interpret it.

#### Raw `JSONField` template_data

If you keep `template_data` as a plain `JSONField` (no schema), no automatic URL handling is performed on the way out. The supported render paths in that mode are:

- Django templates: `{% load camomilla_filters %}{% localized_url page.template_data.cta_url %}`
- JS frontends: resolve client-side using the active language prefix (the `@camomillacms/astro-integration` ships a helper)

Typed schemas with `Permalink` are the recommended path for new code — they keep both render targets aligned without per-consumer work.

## How to register translations

```python
# myapp/translation.py
from modeltranslation.translator import translator, TranslationOptions
from .models import MyModel

class MyModelTranslationOptions(TranslationOptions):
    fields = ("title", "description")

translator.register(MyModel, MyModelTranslationOptions)
```

For models extending `AbstractPage`, use `AbstractPageTranslationOptions`:

```python
from camomilla.translation import AbstractPageTranslationOptions

class MyPageTranslationOptions(AbstractPageTranslationOptions):
    fields = ("custom_field",)  # additional fields to translate

translator.register(MyPage, MyPageTranslationOptions)
```

## Sitemap

```python
# myproject/urls.py
from django.contrib.sitemaps.views import sitemap
from camomilla.sitemap import camomilla_sitemaps

urlpatterns += [
    path('sitemap.xml', sitemap, {'sitemaps': camomilla_sitemaps}),
]
```

To customize:

```python
from camomilla.sitemap import CamomillaPagesSitemap

class MySitemap(CamomillaPagesSitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        # ``items()`` returns a ``UrlNode`` queryset already filtered to
        # ``is_public=True`` — it does NOT have the Page-manager lifecycle
        # helpers (``.public()`` etc.). Narrow it with UrlNode-level filters.
        return super().items()
```

## Settings reference

```python
CAMOMILLA = {
    "PROJECT_TITLE": "",
    "ROUTER": {
        "BASE_URL": "",  # subpath for camomilla (e.g. "/cms")
    },
    "MEDIA": {
        "OPTIMIZE": {
            "MAX_WIDTH": 1980,
            "MAX_HEIGHT": 1400,
            "DPI": 30,
            "JPEG_QUALITY": 85,
            "ENABLE": True,
        },
        "THUMBNAIL": {
            "FOLDER": "",
            "WIDTH": 50,
            "HEIGHT": 50,
        },
    },
    "RENDER": {
        "TEMPLATE_CONTEXT_FILES": [],  # paths to custom context files
        "AUTO_CREATE_HOMEPAGE": True,
        "REGISTERED_TEMPLATES_APPS": [],  # apps to discover templates from
        "ARTICLE": {
            "DEFAULT_TEMPLATE": "",
            "INJECT_CONTEXT": None,
        },
        "PAGE": {
            "DEFAULT_TEMPLATE": "",
            "INJECT_CONTEXT": None,
        },
    },
    "API": {
        "NESTING_DEPTH": 10,  # default depth for nested serializers
        "TRANSLATION_ACCESSOR": "translations",
        "PAGES": {
            "ROUTER_CACHE": 900,  # pages-router cache in seconds (15 min)
        },
    },
    "STRUCTURED_FIELD": {
        "CACHE_ENABLED": True,
    },
    "DEBUG": False,
}
```

## Essential commands

```bash
python manage.py makemigrations camomilla  # after upgrading camomilla
python manage.py migrate
python manage.py regenerate_thumbnails     # regenerate all media thumbnails
```

## Common mistakes — never do these things

1. **Don't put `dynamic_pages_urls` before other URLs.** It's a catch-all: it intercepts EVERYTHING that doesn't match. It MUST always be the last pattern in `urlpatterns`.

2. **Don't create raw `ModelSerializer` instead of `BaseModelSerializer`.** You lose: nested translations, auto-nesting relations, pagination, filters, query optimization. Always use `BaseModelSerializer`.

3. **Don't forget `AbstractPageMixin` in page serializers.** Without it, permalink, breadcrumbs, routerlink, and unique permalink validation are missing.

4. **Don't use `TranslationOptions` for page models.** Use `AbstractPageTranslationOptions` which already includes all necessary SEO and page fields. Without it, base page fields won't be translated.

5. **Don't declare `queryset` as a static class attribute in viewsets with translations.** With modeltranslation, a static queryset doesn't reflect the active request language. If you need a custom queryset, override `get_queryset()`.

6. **Don't use `ForeignKey(Media)` with `on_delete=models.CASCADE`.** Use `on_delete=models.SET_NULL` with `null=True, blank=True`. Deleting a media file should not cascade-delete objects referencing it.

7. **Don't forget the `camomilla_migrations/` folder.** Camomilla is an installed package: its migrations can't live in the package. Create the folder and configure `MIGRATION_MODULES`.

8. **Don't use `Date` types in JSON fields for StructuredJSONField.** Use standard Pydantic types (`str`, `int`, `float`, `bool`, Django models for FK, `QuerySet[Model]` for M2M). Datetime types are not natively supported in the JSON schema.

9. **`status` is a derived property, not a column — but `.filter(status=...)` still works.** The column was removed; the manager rewrites `Page.objects.filter(status="PUB")` / `.exclude(status="TRS")` / `.filter(is_public=True)` into the equivalent timestamp conditions, so upgrading code keeps working. Caveats: only keyword lookups on `filter`/`exclude`/`get` are rewritten — `status` wrapped in a `Q()`, or `order_by("status")` / `values("status")`, is **not**; use `.with_lifecycle()` (the `computed_status` annotation) there. The explicit helpers `.public()` / `.draft()` / `.scheduled()` / `.trashed()` / `.alive()` remain the clearest way to express intent.

10. **Don't mutate drafts via raw page fields.** There's no `publish_at` or `draft_data` column anymore — those live on the separate `Draft` model. Use `page.save_draft(data)` / `page.discard_draft()` / `page.publish()` / `page.schedule(when)`, or the API actions under `/api/camomilla/pages/{id}/`.

11. **Don't trash to hide a single language.** `deleted_at` is global. To 404 just one language, clear that language's `published_at`: `set_nofallbacks(page, "published_at", None, language="en")` then `page.save()`.

12. **Don't forget to schedule the cron command.** Lazy materialization handles pages with traffic, but `python manage.py camomilla_publish_scheduled` is the safety net for pages no one visits. Run it from cron / Celery beat / similar.
