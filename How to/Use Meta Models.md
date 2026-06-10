---
url: /camomilla-core/How to/Use Meta Models.md
---
# 🗂️ Use Meta Models

Meta models let **editors define new content types at runtime** via the admin — no new Django models or migrations required. A **MetaType** declares a list of typed fields; a **MetaInstance** holds concrete data validated against the chosen type.

Typical use cases: FAQs, testimonials, team members, product specs, pricing tables — any schema that varies per project or needs to evolve without developer involvement.

***

## How it works

1. An editor creates a **MetaType** (e.g. `faq`) and declares its fields using a structured editor in the admin.
2. The editor creates **MetaInstance** records selecting that type. The form automatically adapts to the declared fields.
3. At save time, the `data` JSON is validated against a Pydantic model compiled at runtime from the MetaType definition.
4. The frontend fetches `data` via REST API, optionally reading the JSON Schema to drive its own form rendering.

***

## Field kinds

| Kind | Stored as | Notes |
|---|---|---|
| `string` | `str` | Single-line text |
| `text` | `str` | Multi-line text |
| `integer` | `int` | |
| `number` | `float` | |
| `boolean` | `bool` | |
| `date` | ISO date string | |
| `datetime` | ISO datetime string | |
| `media` | PK → `camomilla.Media` instance | |
| `ref` | PK → any installed Django model | Requires `target_model` = `"app.ModelName"` |
| `group` | nested object | Requires `children` |
| `list` | array of objects | Requires `children` |

***

## Creating a MetaType in the admin

1. Go to **Admin → Meta types → Add**.
2. Set a unique `key` (slug) and a `name`.
3. In the **Schema** editor, add field rows. Each row has:
   * **name** — the JSON key
   * **label** — human-readable label
   * **kind** — field type (see table above)
   * **required** / **translated** toggles
   * **target\_model** *(visible only when `kind = ref`)* — select from all installed models
   * **children** *(visible only when `kind = group` or `list`)* — nested field definitions

***

## Creating a MetaType via API

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

***

## Creating a MetaInstance via API

```http
POST /api/camomilla/meta-instances/
Content-Type: application/json

{
    "meta_type": 1,
    "identifier": "faq-what-is-camomilla",
    "data": {
        "question": {"en": "What is camomilla?", "it": "Cos'è camomilla?"},
        "answer":   {"en": "A headless CMS.",    "it": "Un CMS headless."},
        "weight": 10
    }
}
```

Translated fields follow the same `{"language_code": value}` format as the rest of the Camomilla API.

Invalid payloads (missing required fields, wrong types) return `400` with field-level error details.

***

## Nested group and list fields

```json
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

The corresponding instance payload:

```json
{
    "meta_type": 2,
    "data": {
        "title": "Widget Pro",
        "attributes": [
            {"label": "Color", "value": "Blue"},
            {"label": "Material", "value": "Aluminium"}
        ],
        "dimensions": {"width": 10.5, "height": 4.0, "depth": 2.0}
    }
}
```

***

## Referencing another Django model

Use `kind = ref` and set `target_model` to `"app_label.ModelName"`:

```json
{
    "name": "author",
    "kind": "ref",
    "target_model": "auth.User",
    "required": true
}
```

The stored PK is resolved to the full object representation in API responses.

***

## Fetching the JSON Schema

Frontends can request the JSON Schema for a MetaType to drive dynamic form rendering without hard-coding field lists.

```http
GET /api/camomilla/meta-instances/schema/?meta_type=1
```

Or directly from the MetaType resource:

```http
GET /api/camomilla/meta-types/1/schema/
```

Both return a standard JSON Schema object that can be fed to any JSON Schema form library.

***

## API endpoints summary

| Endpoint | Method | Description |
|---|---|---|
| `/api/camomilla/meta-types/` | `GET` / `POST` | List or create MetaTypes |
| `/api/camomilla/meta-types/<id>/` | `GET` / `PATCH` / `DELETE` | Retrieve, update or delete a MetaType |
| `/api/camomilla/meta-types/<id>/schema/` | `GET` | JSON Schema for the MetaType |
| `/api/camomilla/meta-instances/` | `GET` / `POST` | List or create MetaInstances |
| `/api/camomilla/meta-instances/<id>/` | `GET` / `PATCH` / `DELETE` | Retrieve, update or delete a MetaInstance |
| `/api/camomilla/meta-instances/schema/?meta_type=<id>` | `GET` | JSON Schema for a given MetaType |

All endpoints support the standard Camomilla query parameters (`?items`, `?sort`, `?search`, `?fields`, `?language`, `?fltr`).

***

## Schema cache

The runtime Pydantic model compiled from a MetaType definition is cached per `(meta_type_id, compiled_at)`. Saving a MetaType — from the admin or via API — invalidates the cache automatically. All subsequent requests use the updated schema immediately with no server restart needed.
