# Camomilla CMS - AI Coding Instructions

## Project Overview

Camomilla is a Django-based headless CMS (v6.x) providing REST APIs for content management, media handling, multilingual support via `modeltranslation`, and a flexible page system with URL routing. Supports Django 4.2-5.2 and Python 3.10-3.14.

---

## Architecture Overview

### Directory Structure
```
camomilla/
├── models/           # Core data models (Page, Media, Article, Menu, Content)
├── serializers/      # DRF serializers with mixin system
│   ├── base/         # BaseModelSerializer combining all mixins
│   ├── mixins/       # Translation, nesting, optimization, JSON patching
│   └── fields/       # Custom field types (RelatedField, FileField)
├── views/            # API viewsets
│   ├── base/         # BaseModelViewset with permissions/pagination
│   └── mixins/       # Pagination, search, permissions, optimization
├── storages/         # Media optimization and storage backends
├── templates_context/# Page context injection system
└── utils/            # Query parsing, translation helpers, getters/setters
```

### Core Data Flow
1. **Request** → `BaseModelViewset` (handles auth, pagination, search, filters)
2. **Serialization** → `BaseModelSerializer` (translations nested, relations expanded)
3. **Response** → JSON with `translations` key for i18n fields, nested related objects

---

## Model System

### AbstractPage Architecture
Pages use a two-model pattern: `AbstractPage` + `UrlNode` for permalink management.

```python
from camomilla.models import AbstractPage

class MyPage(AbstractPage):
    custom_field = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = "My Page"
    
    class PageMeta:
        parent_page_field = "parent_page"  # Or custom FK field
        default_template = "pages/my_page.html"
        inject_context_func = my_context_function  # Optional
        standard_serializer = "myapp.serializers.MyPageSerializer"
```

**Key Page Features:**
- `UrlNode` handles permalinks per-language, auto-generates redirects on URL changes
- Status system: `PUB` (Published), `DRF` (Draft), `TRS` (Trash), `PLA` (Planned)
- `autopermalink=True` generates URLs from title + parent hierarchy
- `is_public` property checks status and publication_date
- `breadcrumbs` property builds navigation path from parent chain

**Page Mixins** ([camomilla/models/mixins/__init__.py](camomilla/models/mixins/__init__.py)):
- `SeoMixin`: title, description, og_*, canonical, keywords fields
- `MetaMixin`: JSON `meta` field with `get_meta()`, `update_meta()`, `delete_meta()`

### Media System
```python
from camomilla.models import Media, MediaFolder

# Media auto-generates thumbnails on save via post_save signal
# Uses OptimizedStorage for automatic image resizing
media = Media.objects.create(file=uploaded_file)
# media.thumbnail, media.mime_type, media.image_props auto-populated
```

**Storage Settings:**
```python
CAMOMILLA = {
    "MEDIA": {
        "OPTIMIZE": {
            "ENABLE": True,
            "MAX_WIDTH": 1980,
            "MAX_HEIGHT": 1400,
            "DPI": 30,
            "JPEG_QUALITY": 85
        },
        "THUMBNAIL": {"WIDTH": 50, "HEIGHT": 50}
    }
}
```

---

## Serializer System

### BaseModelSerializer Composition
[camomilla/serializers/base/__init__.py](camomilla/serializers/base/__init__.py) combines these mixins:
- `TranslationsMixin`: Nests `title_en`, `title_it` → `{"translations": {"en": {"title": ...}}}`
- `NestMixin`: Auto-creates nested serializers for FK/M2M up to `NESTING_DEPTH`
- `JSONFieldPatchMixin`: PATCH requests merge JSONField data instead of replacing
- `SetupEagerLoadingMixin`: Auto-optimizes queries with `select_related`/`prefetch_related`
- `FilterFieldsMixin`: Respects `?fields=id,title` query param
- `OrderingMixin`: Handles `?sort=field&order=asc|desc`

### Custom Serializer Example
```python
from camomilla.serializers.base import BaseModelSerializer

class MyModelSerializer(BaseModelSerializer):
    class Meta:
        model = MyModel
        fields = "__all__"
        depth = 5  # Override nesting depth
    
    # Optional: custom eager loading
    @classmethod
    def setup_eager_loading(cls, queryset, context=None):
        return queryset.select_related("author").prefetch_related("tags")
```

---

## View System

### BaseModelViewset Features
[camomilla/views/base/__init__.py](camomilla/views/base/__init__.py) includes:
- `CamomillaBasePermissionMixin`: Django model permissions (`add_`, `change_`, `delete_`, `view_`)
- `PaginateStackMixin`: `?items=10&page=2` pagination
- `OrderingMixin`: `?sort=field,-other_field`
- `OptimViewMixin`: Query optimization

### Query Parameters
| Param | Example | Description |
|-------|---------|-------------|
| `items` | `?items=10` | Enable pagination, items per page |
| `page` | `?page=2` | Page number |
| `sort` | `?sort=-created,title` | Order by fields (- for desc) |
| `order` | `?order=desc` | Global order direction |
| `search` | `?search=term` | Full-text search (PostgreSQL) or icontains |
| `fields` | `?fields=id,title` | Limit returned fields |
| `language` | `?language=it` | Switch response language |
| `fltr` | `?fltr=status='PUB'` | Filter syntax (see Query Parser) |

### Query Parser Syntax
[camomilla/utils/query_parser.py](camomilla/utils/query_parser.py) - Filter format:
```
?fltr=field='value' AND (status='PUB' OR status='PLA')
?fltr=count__gte=10
?fltr=tags__name__in=[tag1,tag2]
```

---

## API Registration

### Auto-Registration Decorator
```python
from camomilla import model_api

# Basic - creates /api/models/my-model/
@model_api.register()
class MyModel(models.Model):
    title = models.CharField(max_length=200)

# Customized
@model_api.register(
    serializer_meta={"fields": ["id", "name"], "depth": 2},
    viewset_attrs={"search_fields": ["name", "description"]},
    filters={"is_active": True}  # Pre-filter queryset
)
class FilteredModel(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

# Custom base classes
@model_api.register(
    base_serializer=MyCustomSerializer,
    base_viewset=MyCustomViewset
)
class CustomModel(models.Model):
    pass
```

**URL Setup:**
```python
# urls.py
urlpatterns = [
    path('api/camomilla/', include('camomilla.urls')),  # Built-in endpoints
    path('api/models/', include('camomilla.model_api')),  # Registered models
    path('', include('camomilla.dynamic_pages_urls')),  # Page routing (MUST BE LAST)
]
```

---

## Translation System

### API Behavior
Input/output transformation by `TranslationsMixin`:
```python
# Input (POST/PATCH):
{"translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}}
# Transforms to: {"title_en": "Hello", "title_it": "Ciao"}

# Output (GET):
{"title": "Hello", "translations": {"en": {"title": "Hello"}, "it": {"title": "Ciao"}}}
```

### Language Query Params
- `?language=it` - Switch active language for response
- `?included_translations=all` - Include all translation fields
- `?included_translations=en,it` - Include specific languages only

---

## Page Context System

### Template Context Registration
[camomilla/templates_context/rendering.py](camomilla/templates_context/rendering.py):
```python
from camomilla.templates_context.rendering import register

# By template path
@register(template_path="pages/home.html")
def home_context(request, super_ctx):
    return {"featured": Article.objects.filter(featured=True)[:5]}

# By page model class
@register(page_model=MyPage)
def my_page_context(request, super_ctx):
    return {"related": super_ctx["page"].related_items.all()}

# Both
@register(template_path="pages/article.html", page_model=ArticlePage)
def article_context(request, super_ctx):
    return {"sidebar": get_sidebar_content()}
```

### Dynamic Page URLs
[camomilla/dynamic_pages_urls.py](camomilla/dynamic_pages_urls.py):
- Catches all URLs not matched by other patterns
- Looks up `UrlNode` by permalink
- Handles redirects automatically
- Supports `?preview=true` for staff users

---

## Permissions System

[camomilla/permissions.py](camomilla/permissions.py):
```python
class CamomillaBasePermissions:
    # Superusers: full access
    # Authenticated: checks Django model permissions
    # - GET: always allowed (safe methods)
    # - POST: requires `app.add_modelname`
    # - PUT/PATCH: requires `app.change_modelname`
    # - DELETE: requires `app.delete_modelname`
```

---

## Settings Reference

```python
CAMOMILLA = {
    "PROJECT_TITLE": "My CMS",
    "ROUTER": {"BASE_URL": "/cms"},
    "API": {
        "NESTING_DEPTH": 10,
        "TRANSLATION_ACCESSOR": "translations",
        "PAGES": {
            "DEFAULT_SERIALIZER": "camomilla.serializers.mixins.AbstractPageMixin",
            "ROUTER_CACHE": 900  # 15 minutes
        }
    },
    "RENDER": {
        "AUTO_CREATE_HOMEPAGE": True,
        "TEMPLATE_CONTEXT_FILES": ["myapp.contexts"],
        "REGISTERED_TEMPLATES_APPS": ["myapp"],
        "PAGE": {"DEFAULT_TEMPLATE": "pages/default.html"},
        "ARTICLE": {"DEFAULT_TEMPLATE": "articles/default.html"}
    },
    "DEBUG": False
}
```

---

## Development Workflow

### Commands
```bash
make install          # Install deps with uv
make test             # Run pytest + flake8
make format           # Format with black
make lint             # Flake8 only
make migrations       # Generate Django migrations
make migrations-reset # Reset and regenerate all migrations
make clean            # Remove build artifacts
```

### Test Configuration
- Settings: `example/camomilla_example/settings.py`
- Fixtures: `tests/fixtures/`
- Test utilities: `tests/utils/api.py`

```python
import pytest
from rest_framework.test import APIClient
from tests.utils.api import login_superuser, login_user, login_staff

@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_my_feature():
    client = APIClient()
    token = login_superuser()  # Creates user + returns token
    client.credentials(HTTP_AUTHORIZATION="Token " + token)
    
    response = client.post("/api/camomilla/tags/", {"name_en": "Test"})
    assert response.status_code == 201
    
    # Translation assertions
    assert response.json()["translations"]["en"]["name"] == "Test"
```

### Database Support
- SQLite: Uses custom JSONField implementation
- PostgreSQL: Native JSONField + trigram search support

---

## Code Conventions

- **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
- **Formatting**: `black` (enforced)
- **Linting**: `flake8 camomilla` (must pass)
- **Inheritance**: Always use `BaseModelSerializer` and `BaseModelViewset` for new endpoints
- **Permissions**: Apply `CamomillaBasePermissions` to all API viewsets
- **Translations**: Register translatable fields in `translation.py` using `modeltranslation`

---

## Key Files Reference

| File | Purpose |
|------|---------|
| [camomilla/model_api.py](camomilla/model_api.py) | `@model_api.register()` decorator |
| [camomilla/serializers/base/__init__.py](camomilla/serializers/base/__init__.py) | BaseModelSerializer with all mixins |
| [camomilla/views/base/__init__.py](camomilla/views/base/__init__.py) | BaseModelViewset implementation |
| [camomilla/models/page.py](camomilla/models/page.py) | AbstractPage, UrlNode, UrlRedirect |
| [camomilla/models/media.py](camomilla/models/media.py) | Media with auto-thumbnails |
| [camomilla/settings.py](camomilla/settings.py) | All CAMOMILLA.* settings |
| [camomilla/permissions.py](camomilla/permissions.py) | Permission classes |
| [camomilla/dynamic_pages_urls.py](camomilla/dynamic_pages_urls.py) | Page URL routing |
| [camomilla/templates_context/rendering.py](camomilla/templates_context/rendering.py) | Context injection registry |
| [camomilla/utils/query_parser.py](camomilla/utils/query_parser.py) | Filter query syntax parser |
| [conftest.py](conftest.py) | Pytest fixtures and DB setup |
| [example/website/models.py](example/website/models.py) | Example model implementations |
