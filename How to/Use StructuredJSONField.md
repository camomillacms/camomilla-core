---
url: /camomilla-core/How to/Use StructuredJSONField.md
---
# 🧬 Use Structured JSON Field

#### powered by [Django Structured Field](https://github.com/bnznamco/django-structured-field)

The [`StructuredJSONField`](https://github.com/bnznamco/django-structured-field) is a special type of field that allows you to create a structured JSONField.
This kind of field allows you to declare a data structure that will be enforced to the json structure.

To declare a data structure you need to create a class that inherits from `structured.pydantic.models.BaseModel` and declare the fields that you want to use. The Base model is a pydantic model, so you can use all the pydantic features. If you never used pydantic before, you can find the documentation [here](https://pydantic-docs.helpmanual.io/).

Let's see an example:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField

class MyStructuredJSONField(BaseModel):
    name: str
    age: int

class MyModel(models.Model):    
    structured_field = StructuredJSONField(schema=MyStructuredJSONField)
```

In this example we created a model with a StructuredJSONField that will accept only jsons with the following structure:

```json
{
    "name": "string",
    "age": 0
}
```

If you try to save a json with a different structure, the field will raise a `ValidationError`.

### Default value

Since the StructuredJSONField is a JSONField, you can use all the JSONField features, like the `default` parameter:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField

class MyStructuredJSONField(BaseModel):
    name: str
    age: int

class MyModel(models.Model):
    structured_field = StructuredJSONField(schema=MyStructuredJSONField, default={"name": "John", "age": 30})
```

In this example we set a default value for the field. If you try to save a json without the `name` or `age` fields, the field will be populated with the default value.

You can also use a generator as default value:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField

class MyStructuredJSONField(BaseModel):
    name: str
    age: int

def default_value():
    return {"name": "John", "age": 30}

class MyModel(models.Model):    
    structured_field = StructuredJSONField(schema=MyStructuredJSONField, default=default_value)
```

In this example we used a function as default value. The function will be called every time a new instance of the model is created.

## Nesting Models

Structured models can be nested. Let's see an example:

```python
from camomilla.structured import BaseModel

class MyNestedModel(BaseModel):
    name: str
    age: int

class MyOtherNestedModel(BaseModel):
    name: str
    age: int
    children: MyNestedModel
    childrens: List[MyNestedModel]
```

If you need to nest recursively a model, for example a model that as itself as children, you can declare the type as a string:

```python
from camomilla.structured import BaseModel

class MyNestedModel(BaseModel):
    name: str
    age: int
    children: 'MyNestedModel'
    childrens: List['MyNestedModel']
```

## List of StructuredJSONField

If you use a list as a default value, the field will adapt the schema to accept a list of the specified type:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField

class MyStructuredJSONField(BaseModel):
    name: str
    age: int

class MyModel(models.Model):
    structured_field = StructuredJSONField(schema=MyStructuredJSONField, default=list)
```

## Foreign Key Field

There are some special features that you can use with the StructuredJSONField.

If you declare a field with a django model as type, the field will be populated with the instance of the model, as it was a foreign key:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField
from django.contrib.auth.models import User

class MyStructuredJSONField(BaseModel):
    name: str
    age: int
    user: User

```

At database level the json will store only the model primary key, but when you access the field you will get the instance of the model.
Hence we have a fully working relation inside a json field.

## QuerySet Field

You can also use an other special type of field: `camomilla.structured.QuerySet`. This field will store a queryset inside the json field. This is useful when you need to store a list of models. For example:

```python
from structured.pydantic.models import BaseModel
from structured.fields import StructuredJSONField
from structured.pydantic.fields import QuerySet
from django.contrib.auth.models import User

class MyStructuredJSONField(BaseModel):
    name: str
    age: int
    users: QuerySet[User]

```

In this example we declared a field that will store a list of users. The field will be populated with a queryset, so you can use all the django queryset features.
In the json structure the field will store only the primary keys of the models, ordered by the queryset order or insertion order.
When you access the django queryset, the order will be preserved. This means that you can manage queryset ordering just saving the json with data in correct order.

## Permalink field (typed links)

Camomilla ships a ready-made structured type for **links**: `camomilla.types.Permalink`. Use it whenever a schema field holds a navigation target, instead of a bare `str`. It's the same type that powers menu nodes (`MenuNode.link`).

```python
from typing import Optional
from camomilla.types import Permalink, LinkTypes
from structured.pydantic.models import BaseModel

class HeroBlock(BaseModel):
    headline: str = ""
    cta_label: str = ""
    cta: Optional[Permalink] = None
```

`Permalink` is a small **polymorphic** model — a single field that can hold either of two kinds of link, distinguished by its `link_type`:

* **`LinkTypes.relational`** (`"RE"`) — a foreign key to a camomilla `UrlNode` (the editor picks a real page). The JSON stores the `UrlNode` **primary key**, not a URL string.
* **`LinkTypes.static`** (`"ST"`) — a free-form URL string for anything that isn't an internal page: external links, `mailto:`, `tel:`, in-page anchors.

### Why use it instead of a string?

* **Referential integrity.** A relational link tracks the *row*, not the URL. Rename the target page and the link still resolves; delete the target and the FK simply nulls instead of silently breaking.
* **Per-language URLs for free.** Each `Permalink` exposes a read-only `url` computed field that resolves to the active-language routerlink — honoring `i18n_patterns` (adds the `/it/` prefix) and `APPEND_SLASH` (trailing slash). The same stored value renders `/about/` on the default language and `/it/about/` while Italian is active, with **no consumer-side i18n logic**.
* **No round-trip corruption.** `url` is *derived*, never stored. Reading the API response and writing it back stores the same struct unchanged.

### The serialized shape

```json
{
  "link_type": "RE",
  "url_node": 4,
  "page": { "id": 4, "name": "About us", "model": "website.page" },
  "url": "/it/about/"
}
```

`page` and `content_type` are auto-derived from `url_node` — editors only ever set `link_type` plus `static` or `url_node`. Bind your frontend's `href` to `url` (never to `static` directly, so relational links keep working).

### Constructing one in code

```python
from camomilla.types import Permalink, LinkTypes

# relational — points at a camomilla page via its UrlNode
cta = Permalink(link_type=LinkTypes.relational, url_node=about_page.url_node)

# static — any external/non-page URL
cta = Permalink(link_type=LinkTypes.static, static="https://example.com")
```

### Absolute vs relative URLs

The `url` computed field is always **root-relative** (`/it/about/`) — a computed field can't reach the serialization context, so there's no request to build an absolute URI from. When you need an absolute link (sitemaps, emails, server-rendered templates), call `get_url(request)` instead:

```python
link.url                  # "/it/about/"        (root-relative)
link.get_url(request=req) # "https://host/it/about/"  (absolute)
```

## Built-in cache system

Both Foreign Key and QuerySet fields can lead to performance issues. If you have a lot of instances of django models spread all over the json, the field will make several queries to the database to retrieve the related models.

The structured field has a built-in cache system to avoid this problem 🎉.

The cache system will analyze the json and will make only the stricly necessary queries to the database. The cache system is enabled by default, but you can disable it from camomilla settings:

```python
# settings.py

CAMOMILLA = {
    "STRUCTURED_FIELD": {
        "CACHE_ENABLED": False
    }
}
```
