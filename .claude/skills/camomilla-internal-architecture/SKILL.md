---
name: camomilla-internal-architecture
description: >-
  Use when contributing to or modifying camomilla's OWN source code (editing
  files inside the django-camomilla-cms package): package/folder architecture,
  the mixin-composition pattern, code conventions, the page lifecycle / draft /
  preview / scheduling internals, URL resolution and the camomilla.types link
  primitives, adding core models / serializer mixins / view mixins, and the
  test harness. NOT for building an app on top of camomilla as a dependency —
  use the camomilla-usage skill for that.
---

# Camomilla CMS — Internal Architecture Skill

> Django-based headless CMS (v6.x) providing REST APIs, media management, multilingual support, and a flexible page system with URL routing. This skill is for contributing to the camomilla source code.

**When to use this skill vs. the other:** Use **camomilla-internal-architecture** when you're editing files *inside* the `camomilla/` package (models, serializers, views, managers, tests, conventions). Use **camomilla-usage** when you're writing a downstream app that *consumes* camomilla. Rule of thumb: editing `camomilla/...` → this skill; editing `myapp/...` → usage.

## Stack and versions

| Dependency | Version | Impact on code |
|---|---|---|
| Python | >= 3.10, < 3.15 | Modern type hints (Optional, List from typing). No walrus operator required |
| Django | >= 4.2 (no upper pin; 4.2–5.2 are classifier-declared + CI-tested) | Multi-version support: don't use APIs deprecated in 4.2 or removed in 5.x |
| djangorestframework | >= 3.10, < 3.17 | Base for the entire API layer |
| django-modeltranslation | >= 0.19.17, < 0.20.0 | Dynamically generated translated fields (e.g. `title_en`, `title_it`) |
| pydantic | >= 2.10.3 | Used via `django-structured-json-field` for typed JSON schemas |
| django-structured-json-field | >= 1.5.1 | `StructuredJSONField` with Pydantic validation + conditional logic helpers |
| Pillow | >= 9.1.0, < 12.0.0 | Image optimization and thumbnails |
| python-magic | >= 0.4, < 0.5 | Media MIME type detection |
| inflection | >= 0.5.1 | Name conversion (used internally) |
| **Dev** | | |
| pytest / pytest-django | >= 3.9.1 / >= 4.11.1 | Test framework |
| black | == 25.9.0 | Formatter (pinned version) |
| flake8 | >= 7.3.0 | Linter (max-line-length=160) |
| responses | == 0.25.8 | Mock HTTP responses in tests |
| python-semantic-release | == 10.4.1 | Automated releases from conventional commits |

**Package manager:** `uv` (Astral). Do not use pip directly.

## Architecture

### Folder structure

```
camomilla/
├── models/              # Core Django models (AbstractPage, Draft, Media, Article, Menu, Content, MetaType, MetaInstance)
│   ├── draft.py         # Draft model: generic FK, per-(page, language) row, holds partial-PATCH payload + scheduled_for
│   └── mixins/          # SeoMixin, MetaMixin
├── serializers/         # DRF serializers
│   ├── base/            # BaseModelSerializer (composition of 7 mixins)
│   ├── mixins/          # TranslationsMixin, NestMixin, OptimizeMixin, page.AbstractPageMixin, etc.
│   ├── fields/          # Custom RelatedField, FileField, ImageField
│   └── utils.py         # Factory: build_standard_model_serializer(), get_editable_bases()
├── views/               # DRF ViewSets
│   ├── base/            # BaseModelViewset (composition of 4 mixins + ModelViewSet)
│   ├── mixins/          # PaginateStackMixin, OptimViewMixin, BulkDeleteMixin, TrigramSearchMixin (PostgreSQL trigram search lives in pagination.py), etc.
│   ├── pages.py         # PageViewSet (CRUD + draft/publish/schedule/preview/render/revisions/revert actions); pages_router + pages_router_preview (share _resolve_route_request)
│   └── decorators.py    # @active_lang(), @staff_excluded_cache()
├── managers/            # Custom QuerySets and Managers (PageQuerySet, UrlNodeManager). NB: DraftQuerySet lives in models/draft.py, not here
├── storages/            # OptimizedStorage for image resizing
├── templates_context/   # Page context injection system (@register)
├── utils/               # Utilities: translation, getters, setters, query_parser
├── contrib/             # Integrations (modeltranslation)
├── fields/              # Custom Django fields (json.py)
├── types.py             # Pydantic types for template_data schemas — Permalink (polymorphic link: UrlNode FK | static string), LinkTypes
├── apps.py              # CamomillaConfig.ready(): migration module injection, context autodiscover, reversion auto-register
├── openapi/             # OpenAPI schema generator
├── theme/               # Admin customization (templates, static, admin classes)
├── templatetags/        # Django template tags (menus: render_menu/node_url; camomilla_filters: localized_url — both request-aware for absolute URLs)
├── management/commands/ # manage.py commands (regenerate_thumbnails, camomilla_publish_scheduled)
├── preview.py           # Scheduled-publish worklist (resolve_scheduled_pages); reversion_available()
├── model_api.py         # @model_api.register() decorator for auto-API
├── settings.py          # CAMOMILLA settings reader from django settings
├── permissions.py       # CamomillaBasePermissions
├── urls.py              # Main DRF router
├── translation.py       # modeltranslation registration for core models
├── dynamic_pages_urls.py # Catch-all URL resolver for pages (HTML render route)
├── sitemap.py           # Sitemap generation
└── redirects.py         # Automatic redirect handling
```

### Mental model

The flow of an API request follows this path:

```
Request → urls.py (DefaultRouter)
        → BaseModelViewset (auth + pagination + search + filters + optimization)
        → BaseModelSerializer (translations + nesting + eager loading + field filtering)
        → JSON Response
```

**Where to put what:**
- Business logic → in models or managers
- Data transformation → in serializers or serializer mixins
- Endpoint behavior → in viewsets or view mixins
- Cross-cutting logic → in decorators (`views/decorators.py`)
- Complex queries → in managers (`managers/`)

### Key architectural pattern: mixin composition

Camomilla does NOT use deep inheritance. It uses **mixin composition** with unpacking in class bases:

```python
# camomilla/serializers/base/__init__.py
bases = (
    SetupEagerLoadingMixin,
    NestMixin,
    FilterFieldsMixin,
    FieldsOverrideMixin,
    JSONFieldPatchMixin,
    OrderingMixin,
)
if ENABLE_TRANSLATIONS:
    bases += (TranslationsMixin,)

class BaseModelSerializer(*bases, serializers.ModelSerializer):
    pass
```

```python
# camomilla/views/base/__init__.py
base_viewset_classes = [
    CamomillaBasePermissionMixin,
    OptimViewMixin,
    OrderingMixin,
    PaginateStackMixin,
    viewsets.ModelViewSet,
]

class BaseModelViewset(*base_viewset_classes):
    metadata_class = BaseViewMetadata
```

This pattern repeats everywhere. New functionality is added as a new mixin in the `bases` tuple.

## Code conventions

### Naming

| What | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `query_parser.py`, `filter_fields.py` |
| Classes | `PascalCase` | `BaseModelSerializer`, `PaginateStackMixin` |
| Mixins | `PascalCase` + `Mixin` suffix | `TranslationsMixin`, `OptimViewMixin` |
| ViewSets | `PascalCase` + `ViewSet` suffix | `ArticleViewSet`, `MediaFolderViewSet` |
| Serializers | `PascalCase` + `Serializer` suffix | `TagSerializer`, `ArticleSerializer` |
| Functions/methods | `snake_case` | `get_queryset()`, `handle_pagination()` |
| Private/cached attrs | Double underscore prefix | `__cached_db_instance`, `__url_node_history__` |
| URL basenames | kebab-case | `camomilla-page`, `camomilla-media` |
| URL paths | kebab-case | `/media-folders/`, `/pages-router/` |
| Related names | `%(app_label)s_%(class)s_<name>` | `"%(app_label)s_%(class)s_highlight_images"` |
| Page lifecycle labels | 3-char uppercase | `PUB`, `DRF`, `TRS`, `PLA` — derived at read time, not stored. See "Page lifecycle architecture" below. |

### Module structure

**Imports:** `__init__.py` uses wildcard imports to expose the module's public API:

```python
# camomilla/models/__init__.py
from .article import *  # NOQA
from .content import *  # NOQA
from .draft import Draft  # NOQA
from .media import *  # NOQA
from .page import *  # NOQA
from .menu import *  # NOQA
```

**Import order in files:** stdlib → Django → DRF → camomilla (relative imports for same package):

```python
# camomilla/views/articles.py
from camomilla.models import Article
from camomilla.serializers import ArticleSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin
```

**Exports:** several package `__init__.py` files define `__all__` — `fields/`, `managers/`, `serializers/{base,fields,mixins}/`, `storages/`, `theme/admin/`, `views/mixins/`. The rest rely on wildcard imports from the package's `__init__.py` as a barrel.

### Recurring patterns

**Concrete ViewSet** — always this schema:

```python
# camomilla/views/articles.py
class ArticleViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    search_fields = ["title", "identifier", "content", "permalink"]
    model = Article
```

**Concrete Serializer** — for regular models:

```python
# camomilla/serializers/article.py
class TagSerializer(BaseModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
```

**Page Serializer** — uses `AbstractPageMixin`:

```python
class ArticleSerializer(AbstractPageMixin, BaseModelSerializer):
    class Meta:
        model = Article
        fields = "__all__"
```

**Model with abstract base** — Abstract + Concrete pattern:

```python
# camomilla/models/article.py
class AbstractArticle(AbstractPage):
    content = models.TextField(default="")
    author = models.ForeignKey(
        dj_settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL
    )
    highlight_image = models.ForeignKey(
        "camomilla.Media", blank=True, null=True, on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_highlight_images",
    )
    tags = models.ManyToManyField("Tag", blank=True)

    class Meta:
        abstract = True
        ordering = ["ordering"]

class Article(AbstractArticle):
    class PageMeta:
        default_template = settings.ARTICLE_DEFAULT_TEMPLATE
        inject_context_func = settings.ARTICLE_INJECT_CONTEXT_FUNC
```

**Translation registration** — core models in `camomilla/translation.py`:

```python
from modeltranslation.translator import TranslationOptions, register

class AbstractPageTranslationOptions(SeoMixinTranslationOptions):
    # ``published_at`` is translatable: each language has its own
    # ``published_at_<lang>`` column. ``deleted_at`` is intentionally NOT
    # here — soft-delete is global. There is no ``status`` field (derived).
    fields = ("breadcrumbs_title", "autopermalink", "indexable", "template_data", "published_at")

@register(Article)
class ArticleTranslationOptions(AbstractPageTranslationOptions):
    fields = ("content",)
```

**Dynamic serializer/viewset creation** — `model_api.py` uses `type()`:

```python
serializer = type(
    f"{model.__name__}Serializer",
    (base_serializer,),
    {"Meta": type("Meta", (), {**base_meta, **serializer_meta})},
)
```

**Signal handler** — `@receiver` for lifecycle events:

```python
@receiver(post_delete, sender=MyModel)
def cleanup_handler(sender, instance, **kwargs):
    # cleanup logic
```

**PageBase metaclass** — dynamically generates `permalink_<lang>` properties on AbstractPage. Do not modify without understanding how `UrlNode` manages per-language permalinks.

## Meta Models — lives in an external package

Meta Models (editor-defined, runtime-typed content) are **not** in the camomilla repo. They were extracted into the standalone **`django-structured-metaobjects`** package (`pyproject.toml` dep `django-structured-metaobjects>=1.0.0`; local checkout at `/Volumes/Development/Lotrek/Projects/structured/django-structured-metaobjects`).

What camomilla itself does with Meta Models — and nothing more:

- **Mounts the viewsets** in `camomilla/urls.py`: `from structured_metaobjects.views import MetaInstanceViewSet, MetaTypeViewSet`, registered under the camomilla API namespace. The import is unconditional — camomilla hard-depends on the package, so `include('camomilla.urls')` fails if it isn't installed.
- That's it. There is **no** `camomilla/meta/`, no `camomilla/models/meta.py`, no `camomilla/views/meta.py`, no `camomilla/theme/admin/meta.py`. Do not look for them in this repo.

To change Meta Models behavior (the `MetaFieldKind` enum, `MetaTypeFieldDef`, the runtime Pydantic compiler, the `MetaType`/`MetaInstance` models, conditional schema logic), work in the `django-structured-metaobjects` repo. Its layout:

- `structured_metaobjects/schema_builder.py` — `MetaFieldKind` enum + `MetaTypeFieldDef` (the editor-facing per-field schema).
- `structured_metaobjects/compiler.py` — builds a runtime Pydantic model from a `MetaType.schema`, with a process-level cache.
- `structured_metaobjects/models.py` — the `MetaType` / `MetaInstance` Django models.
- `structured_metaobjects/views.py` — `MetaTypeViewSet` / `MetaInstanceViewSet` (the ones camomilla mounts).

The real `MetaFieldKind` values are `string`, `html`, `number`, `boolean`, `date`, `datetime`, `select`, `ref`, `queryset`, `group`, `list` — there is no `text`, `integer`, or `media` kind (those are options on `string` / `number` / `ref`). The consumer-facing reference lives in the camomilla-usage skill's "Built-in field kinds" table.

## Page lifecycle architecture

The page lifecycle is **visibility-only** and derived at read time from two timestamps on the page row plus a separate `Draft` table. There is no `status` column. This is a deliberate design choice — see the design notes at the end of this section for the rationale.

### Source of truth

| Column | Translatable | Meaning |
|---|---|---|
| `published_at` | Yes | When this language's live content went / will go public. `NULL` ⇒ never public. |
| `deleted_at` | No (global) | Soft-delete timestamp. Set ⇒ TRS regardless of `published_at`. |

The `Draft` table (`camomilla.models.draft.Draft`) holds pending edits independently:

```python
class Draft(models.Model):
    content_type = ForeignKey(ContentType, ...)
    object_id = PositiveIntegerField()            # generic FK → any AbstractPage subclass
    content_object = GenericForeignKey("content_type", "object_id")
    language = CharField(max_length=10, default="")  # "" = monolingual / NO_LANGUAGE
    serialized = JSONField(default=dict)          # partial-PATCH-shaped payload
    scheduled_for = DateTimeField(null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        constraints = [UniqueConstraint("content_type", "object_id", "language", name="...")]
        indexes = [Index("scheduled_for")]
        ordering = ["-updated_at"]
```

One `UNIQUE(content_type, object_id, language)` row per (page, language) — `save_draft()` uses `get_or_create` + merge semantics.

### Two implementations, pinned by contract test

The lifecycle label is computed in **two** places — Python (for in-memory checks) and SQL (for filtering / ORDER BY). They run on different substrates so we keep them as parallel implementations rather than a single one:

```python
# camomilla/models/page.py
def _lifecycle_label(self) -> str:
    if get_nofallbacks(self, "deleted_at") is not None:
        return PAGE_STATUS_TRASHED
    now = timezone.now()
    published_at = get_nofallbacks(self, "published_at")
    if published_at is not None and published_at <= now:
        return PAGE_STATUS_PUBLISHED
    if published_at is not None:
        return PAGE_STATUS_SCHEDULED
    return PAGE_STATUS_DRAFT
```

```python
# camomilla/managers/pages.py — PageQuerySet.with_lifecycle()
Case(
    When(deleted_at__isnull=False, then=Value(PAGE_STATUS_TRASHED)),
    When(**{f"{published_col}__lte": now}, then=Value(PAGE_STATUS_PUBLISHED)),
    When(**{f"{published_col}__isnull": False}, then=Value(PAGE_STATUS_SCHEDULED)),
    default=Value(PAGE_STATUS_DRAFT),
)
```

`test_lifecycle_property_matches_db_layer` in `tests/test_page_preview.py` runs every lifecycle scenario × every language and asserts both implementations agree. **This test is load-bearing** — anyone adding a new lifecycle state or changing a rule must extend it.

### Per-language `published_at` semantics

`published_at` lives on the page row but is registered with modeltranslation, so each language has its own column (`published_at_en`, `published_at_it`, …). The route resolvers and `is_public` property read via `get_nofallbacks` / `localized_fieldname` so a request for `/en/foo` only consults `published_at_en`. Per-language dismissal is `set_nofallbacks(page, "published_at", None, language="en")` — IT and other languages stay live.

### Draft scoping and per-language drafts

Draft rows carry their own `language` column. `page.save_draft(data)` writes to the active language; `page.publish()` only applies that language's Draft. No per-language draft siblings on the page row, no `scope_draft_to_active_language` helpers — the column does the scoping.

### Lazy materialization

`page.publish_if_due()` runs on every public read (HTML and JSON router) before serving. It:

1. Checks `Draft.objects.for_(self, language=lang).due_now().exists()` cheaply.
2. Opens an atomic block, `SELECT … FOR UPDATE` on the Draft row (falls back to non-locking on backends that don't support it).
3. Applies the Draft via the publish serializer (`_apply_draft_via_serializer`).
4. Stamps `published_at = now()` if it was `NULL` or in the future (so a never-public page with a due Draft becomes public on first read).
5. Deletes the Draft, refreshes the page in-memory.
6. Catches `ValidationError` / `DatabaseError` — logs a warning and returns `False` so the caller serves the current DB state without erroring.

The lock is on the **Draft row, not the page row** — concurrent readers contend only over the scheduled swap, not over the live read. The cron command (`camomilla_publish_scheduled`) is the safety net for pages no one visits.

### Public-route safety

Both `dynamic_pages_urls.fetch` (HTML) and `views.pages.pages_router` (JSON):

1. Resolve the UrlNode for the requested permalink.
2. Call `page.publish_if_due()` (allows a never-public page with a due Draft to flip to public on the way in).
3. **Then** check `page.is_public` — non-public rows return 404.

The default page serializer (`AbstractPageMixin`) deliberately omits `has_draft` and `has_scheduled_draft` so the public router can't leak "this page has pending edits." The preview action's `_draft_overlay` re-attaches them when serving authors.

### URL resolution and link types

**Language decomposition.** `camomilla.utils.translation.url_lang_decompose(url)` splits a request path into `{language, permalink, url}`. It is a thin wrapper over Django's `get_language_from_path` (the same parser `i18n_patterns` uses) — do **not** reintroduce a hand-rolled language-prefix regex. The router routes are mounted under a plain `include` (not `i18n_patterns`), so the `<path:permalink>` kwarg still carries the language prefix; `url_lang_decompose` is what extracts it. No-prefix paths resolve to `DEFAULT_LANGUAGE`, deliberately mirroring `i18n_patterns(prefix_default_language=False)` so the API and HTML routes agree on the same URL. The resolution is **URL-pure** — it does not consult cookies/`Accept-Language`, so a given URL yields the same response for every visitor (load-bearing for the `staff_excluded_cache` cache key and the canonical-redirect contract).

**Shared resolver.** `pages_router` (public) and `pages_router_preview` (auth `IsAuthenticated`, bypasses `is_public`, overlays the draft via `_draft_overlay` + adds `has_draft`) both call `_resolve_route_request(permalink)` in `views/pages.py`. It returns `(UrlNode, canonical_descriptor | None)`: it activates the path's language, looks up the node (trailing-slash-insensitive), and computes the canonical form via `UrlNode.reverse_url`. When the requested form differs from canonical (missing slash, bare `/it`, lang-subpath without slash), it returns a `{"redirect": <url>, "status": 301}` descriptor in the **body** (not an HTTP 301). `pages_router` checks `is_public` **before** honoring that descriptor so non-public rows can't be probed via the redirect.

**Preview must not mutate.** `pages_router_preview` and the by-id `PageViewSet.preview` / `render_preview` actions deliberately do **not** call `publish_if_due()` — a preview shows the *current* pending state, and running the lazy publish would consume a due draft as a side effect of looking at it. Only the public routes (`pages_router`, `dynamic_pages_urls.fetch`) materialize due drafts. Keep it that way.

**Type-driven link localization.** URL-bearing fields inside typed `template_data` are localized by the **`camomilla.types.Permalink` type**, not by a serializer walk. `Permalink` is a polymorphic pydantic model (shared with `MenuNode.link` — `MenuNodeLink` is now an alias): `link_type=relational` holds a `UrlNode` FK, `link_type=static` holds a free string. Its `url` computed field returns the active-language routerlink. The old approach — `AbstractPageMixin.to_representation` recursively walking `template_data` to rewrite permalink strings (`_collect_permalink_candidates` / `_resolve_permalinks`) — was **removed**; do not reintroduce a JSON-tree walk. Raw (unschematized) `JSONField` `template_data` has no auto-localization; it relies on the `localized_url` template tag at render time.

**Request threading for absolute URIs.** `UrlNode.reverse_url(permalink, request=None)` builds an absolute URI when given a request (homepage branch included). `UrlNode.get_routerlink(request)`, `Permalink.get_url(request)`, the `localized_url` tag (`takes_context=True`), and the `node_url:request` filter arg all thread it through; `Menu.render` always binds `request` (even `None`) into the menu context so `{{ item|node_url:request }}` never raises. The `Permalink.url` computed field stays root-relative by design — a pydantic computed field can't reach the serialization context, so absolute URLs require the explicit `get_url(request)` path.

### Apply path — partial-PATCH semantics

`_apply_draft_via_serializer(draft_data)` runs the Draft's payload through the same serializer the API uses for PATCH:

```python
serializer_cls = build_standard_model_serializer(
    self.__class__,
    bases=get_editable_bases(self.__class__.get_serializer()),
    name_suffix="Draft",
)
serializer = serializer_cls(instance, data=draft_data, partial=True)
serializer.is_valid(raise_exception=True)
serializer.save()
```

Validation happens at apply time, not at save time. This means a Draft with stale FK targets fails on publish (loudly), not silently. The trade-off: drafts can't be authored from the Django admin form output directly — that form produces full-snapshot data, not partial-PATCH data. The admin observes drafts (via the Draft Inspector and action buttons) but does not author them.

### Scheduling semantics

`page.schedule(when)` branches on whether the active language has ever been public:

| State | Behavior |
|---|---|
| `published_at IS NULL` | Sets `published_at = when` directly. No Draft needed: the live row IS the future content. |
| `published_at IS NOT NULL` | Attaches `scheduled_for = when` to the existing Draft. The live row stays visible until `when`. **A Draft must exist** (call `save_draft` first); otherwise the method warns + no-ops. |

### Cron worklist — `camomilla.preview.resolve_scheduled_pages`

```python
def resolve_scheduled_pages():
    for draft in Draft.objects.due_now().select_related("content_type"):
        page = draft.content_type.get_object_for_this_type(pk=draft.object_id)
        yield page, draft.language
```

Yields `(page, language)` pairs from the Draft table directly. The management command `camomilla_publish_scheduled` iterates this and calls `publish_if_due()` per pair, activating each language with try/finally.

### Why no `status` column

Before the refactor: `status` (ChoiceField), `publish_at` (translatable), `draft_data` (translatable), `has_draft` (translatable) all coexisted as columns. Every transition had to sync them; per-language siblings doubled the surface. The schema was vulnerable to "the label lies" drift (`status="PUB"` while `published_at IS NULL` was representable).

The current design eliminates that class of bug by making the label a function of the underlying state. The cost: two implementations to keep aligned (covered by the contract test), a hand-written `LifecycleStatusFilter` for admin, and a more demanding mental model for newcomers. The win is correctness — see the `test_lifecycle_property_matches_db_layer` scenarios for the full enumeration this design encodes.

## How to add a new core model

Step-by-step to add a new model to camomilla (e.g. `Product`):

### 1. Create the model (`camomilla/models/product.py`)

```python
from django.db import models
from camomilla.models.page import AbstractPage

class AbstractProduct(AbstractPage):
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=100, unique=True)

    class Meta:
        abstract = True
        ordering = ["ordering"]

class Product(AbstractProduct):
    class PageMeta:
        default_template = "defaults/pages/product.html"
```

### 2. Export from the package (`camomilla/models/__init__.py`)

```python
from .product import *  # NOQA
```

### 3. Register translations (`camomilla/translation.py`)

```python
from camomilla.models import Product

@register(Product)
class ProductTranslationOptions(AbstractPageTranslationOptions):
    fields = ()  # add custom translated fields if needed
```

### 4. Create the serializer (`camomilla/serializers/product.py`)

```python
from camomilla.models import Product
from camomilla.serializers.base import BaseModelSerializer
from camomilla.serializers.mixins import AbstractPageMixin

class ProductSerializer(AbstractPageMixin, BaseModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
```

Export: add `from .product import *` in `camomilla/serializers/__init__.py`

### 5. Create the viewset (`camomilla/views/products.py`)

```python
from camomilla.models import Product
from camomilla.serializers import ProductSerializer
from camomilla.views.base import BaseModelViewset
from camomilla.views.mixins import BulkDeleteMixin, GetUserLanguageMixin

class ProductViewSet(GetUserLanguageMixin, BulkDeleteMixin, BaseModelViewset):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    search_fields = ["title", "sku"]
    model = Product
```

Export: add `from .products import *` in `camomilla/views/__init__.py`

### 6. Register the route (`camomilla/urls.py`)

```python
router.register("products", ProductViewSet, "camomilla-product")
```

### 7. Write tests (`tests/test_product.py`)

See Testing section.

## How to add a new serializer mixin

1. Create `camomilla/serializers/mixins/my_mixin.py`
2. The mixin should override `serializers.Serializer` methods (e.g. `to_representation`, `to_internal_value`)
3. Export from `camomilla/serializers/mixins/__init__.py`
4. Add to the `bases` tuple in `camomilla/serializers/base/__init__.py` — order matters (MRO)

## How to add a new view mixin

1. Create `camomilla/views/mixins/my_mixin.py`
2. Export from `camomilla/views/mixins/__init__.py`
3. Add to the `base_viewset_classes` list in `camomilla/views/base/__init__.py` or use directly in concrete viewsets

## Internal dependencies — always use these

| Utility | Location | When to use |
|---|---|---|
| `pointed_getter(obj, "path.to.key")` | `camomilla/utils/getters.py` | Nested access in dicts or objects with dot-notation |
| `safe_getter(obj, key, default)` | `camomilla/utils/getters.py` | Dict/object agnostic getter (uses `getattr` or `[]`) |
| `activate_languages()` | `camomilla/utils/translation.py` | Context manager to temporarily activate a language |
| `plain_to_nest()` / `nest_to_plain()` | `camomilla/utils/translation.py` | Transform flat fields (`title_en`) to/from nested structure (`translations.en.title`) |
| `is_translatable(model)` | `camomilla/utils/translation.py` | Check if a model is registered with modeltranslation |
| `build_standard_model_serializer(model, depth)` | `camomilla/serializers/utils.py` | Factory to create serializers on the fly with `type()` |
| `get_standard_bases()` | `camomilla/serializers/utils.py` | Returns the standard mixin tuple for dynamic serializers |
| `ConditionParser` | `camomilla/utils/query_parser.py` | Parser for the `?fltr=field='value'` syntax |
| `camomilla.settings` | `camomilla/settings.py` | Access all CAMOMILLA settings with fallbacks. Uses `pointed_getter` internally |

## Testing

### Framework and configuration

- **Framework:** pytest + pytest-django
- **Settings:** `example/camomilla_example/settings.py` (configured in `pytest.ini`)
- **Test dir:** `tests/`
- **Naming:** `test_*.py`
- **Fixtures dir:** `tests/fixtures/` (JSON and file assets)
- **Utilities:** `tests/utils/api.py` (auth helpers), `tests/utils/media.py` (asset loaders)

### Test pattern

Every test function must have this decorator:

```python
@pytest.mark.django_db(transaction=True, reset_sequences=True)
```

**Real example** (from `tests/test_api.py`):

```python
import pytest
from rest_framework.test import APIClient
from tests.utils.api import login_superuser
from camomilla.models import Tag

client = APIClient()

@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_crud_tag():
    # Auth
    token = login_superuser()
    client.credentials(HTTP_AUTHORIZATION="Token " + token)

    # Create
    response = client.post("/api/camomilla/tags/", {"name_en": "First tag"})
    assert response.status_code == 201
    assert response.json()["name"] == "First tag"
    assert len(Tag.objects.all()) == 1

    # Verify translations
    response = client.post("/api/camomilla/tags/", {"name_it": "Secondo tag"})
    assert response.json()["translations"]["it"]["name"] == "Secondo tag"

    # Update with nested translations
    response = client.patch(
        "/api/camomilla/tags/2/",
        {"translations": {"en": {"name": "Second tag"}}},
        format="json",
    )
    assert response.json()["translations"]["en"]["name"] == "Second tag"

    # Delete
    response = client.delete("/api/camomilla/tags/2/")
    assert response.status_code == 204
```

**Test conventions:**
- Object creation: **always via direct ORM** (`Model.objects.create()`) or via API. No factory libraries
- Auth: use `login_superuser()`, `login_user()`, `login_staff()` from `tests/utils/api.py`
- Client: DRF's `APIClient()`, authentication via token header
- Assertions: status code + JSON body + DB state
- Translated fields in POST: use the language suffix (`name_en`, `title_it`)
- JSON format in PATCH: explicit `format="json"`

### Execution

```bash
make test    # flake8 + pytest with coverage
make lint    # flake8 only
```

CI tests on: Python 3.10-3.14 x Django 4.2/5.1/5.2 x SQLite/PostgreSQL/MySQL.

## Essential commands

```bash
make install           # uv sync --dev
make test              # flake8 + pytest + coverage
make format            # black .
make lint              # flake8 camomilla
make migrations        # makemigrations + migrate
make migrations-reset  # reset and regenerate all migrations
make clean             # remove artifacts
```

## Common mistakes — never do these things

1. **Don't create serializers without extending BaseModelSerializer.** All serializers must go through the mixin chain (translations, nesting, optimization). Creating a raw `serializers.ModelSerializer` breaks the API contract.

2. **Don't create viewsets without extending BaseModelViewset.** Same reason: pagination, search, permissions are in the base viewset mixins.

3. **Don't forget modeltranslation registration.** If you add a model with text fields, register it in `camomilla/translation.py`. Without registration, `TranslationsMixin` won't transform the fields and the API returns flat data.

4. **Don't use `AbstractPageMixin` for non-page models.** `AbstractPageMixin` adds permalink, breadcrumbs, and routerlink fields. Only use it for models extending `AbstractPage`.

5. **Don't use `pip install`.** The project uses `uv`. Use `make install` or `uv sync --dev`.

6. **Don't ignore multi-database support.** Tests run on SQLite, PostgreSQL, and MySQL. Some features (trigram search, `SearchVector`) are PostgreSQL-only and have fallbacks for other DBs. Verify your code works on SQLite.

7. **Don't use factory libraries in tests.** The project creates objects via direct ORM. Don't introduce `factory_boy` or similar.

8. **Don't modify the mixin system without understanding MRO.** The order in the `bases` tuple determines which mixin overrides which. Adding a mixin in the wrong position breaks the chain.

9. **Don't use `queryset = Model.objects.all()` as a class attribute in viewsets with translations.** With modeltranslation, a static queryset doesn't reflect the active language. Use `get_queryset()` if you need customization. Camomilla's base viewsets handle this internally.

10. **Don't use `print` in tests.** Recent commits show removal of debug `print` statements from tests. Use assertions.

11. **Don't add a `status` column back to AbstractPage.** It was removed deliberately — the label is derived from `published_at` + `deleted_at` + the `Draft` table. Adding it would reintroduce the "label lies" drift class. If you add a new lifecycle state, extend both `_lifecycle_label()` (Python) and `with_lifecycle()` (SQL `Case/When`), and add the scenario to `test_lifecycle_property_matches_db_layer`.

12. **Don't expose `has_draft` / `has_scheduled_draft` on the default page serializer.** They're omitted from `AbstractPageMixin` so the public `pages-router` can't reveal whether a page has pending edits. They're attached by the preview action's `_draft_overlay` only.

13. **Don't bypass `is_public` on the public routes.** Both `dynamic_pages_urls.fetch` and `views.pages.pages_router` gate every response on `page.is_public` after `publish_if_due()`. Trashed, draft, and scheduled-first-publish rows must 404. If you add a new public surface (e.g. sitemap, RSS), apply the same gate.

14. **Don't add per-language draft columns.** The whole point of the `Draft` model is one auxiliary table, scoped via the `language` column. Resist the temptation to add `draft_data_<lang>` siblings on a subclass — it brings back the drift class the Draft model eliminated.

## Environment variables

The project uses environment variables only for multi-database testing:

| Variable | Default | Usage |
|---|---|---|
| `DATABASE_ENGINE` | `sqlite` | Selects the DB for tests: `sqlite`, `postgres`, `mysql` |
| `DATABASE_NAME` | (depends on engine) | Database name |
| `DATABASE_USER` | (depends on engine) | Database user |
| `DATABASE_PASSWORD` | (depends on engine) | Database password |
| `DATABASE_HOST` | `localhost` | Database host |
| `DATABASE_PORT` | (depends on engine) | Database port |
