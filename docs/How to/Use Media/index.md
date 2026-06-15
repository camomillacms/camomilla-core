# 🖼️ Use Media 

Camomilla has full media management.
Everything is stored in the Media model. 

To attach medias to a custom model just assign a ForeignKey or a ManyToMany relation.

```python
class MyModel(models.Model):
    image = models.ForeignKey(
        "camomilla.Media",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    gallery = models.ManyToManyField("camomilla.Media", blank=True)
```

Every media can be associated to a MediaFolder.
The MediaFolder is a tree structure of folders (like a fs).

The media takes care of optimizing images. The optimization consists in a resize to a max width-height and to a DPI scaling. You can disable optimization or change sizes and dpi from settings:

```python
CAMOMILLA = {
    "MEDIA": {
        "OPTIMIZE": {"MAX_WIDTH": 1980, "MAX_HEIGHT": 1400, "DPI": 30, "ENABLE": True},
    },
}
```

Camomilla creates also image thumbnails. You can change, thumbnails size from settings:
```python
CAMOMILLA = {
    "MEDIA": {
        "THUMBNAIL": {"FOLDER": "", "WIDTH": 50, "HEIGHT": 50}
    },
}
```

## 📐 Responsive Renditions (srcset)

In addition to the single optimized original and the thumbnail, Camomilla can generate a configurable set of **responsive image renditions** — width-based, multi-format variants ready to be dropped into an `<img srcset>` or `<picture>` tag. Renditions are produced on upload (and on demand), stored next to the original, and exposed via the REST API in a shape a frontend can consume without any extra processing.

### Default configuration

Out of the box, every uploaded image produces **9 renditions** (3 widths × 3 formats):

| Name | Width | Format |
|---|---|---|
| `sm-webp`, `md-webp`, `lg-webp` | 400 / 800 / 1600 | WebP |
| `sm-avif`, `md-avif`, `lg-avif` | 400 / 800 / 1600 | AVIF |
| `sm-original`, `md-original`, `lg-original` | 400 / 800 / 1600 | source format (JPEG/PNG) |

Renditions that would upscale the original (target width ≥ source width) are skipped. Renditions whose encoded output is larger than the source are also skipped (inflate guard).

> [!NOTE]
> AVIF requires the optional `pillow-avif-plugin` dependency. Without it, AVIF renditions are silently omitted — all other formats still generate. Install with `pip install "django-camomilla-cms[avif]"`.

### Settings

All rendition settings live under `CAMOMILLA.MEDIA.RENDITIONS`:

```python
CAMOMILLA = {
    "MEDIA": {
        "RENDITIONS": {
            "ENABLE": True,
            "FOLDER": "renditions",
            "VARIANTS": [
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
            "JPEG_QUALITY": 85,
            "WEBP_QUALITY": 82,
            "AVIF_QUALITY": 60,
            "PREVENT_INFLATE": True,
        },
    },
}
```

- **`ENABLE`** — master kill switch. When `False`, no renditions are generated and `media.renditions` stays `{}`.
- **`VARIANTS`** — list of `{name, width, format}` dicts. `format` accepts `"webp"`, `"avif"`, `"jpeg"`, `"png"`, or `"original"` (keep the source format).
- **`FOLDER`** — subfolder of `MEDIA_ROOT` where rendition files live. Each original gets its own directory: `renditions/<stem>/<name>.<ext>`.
- **`PREVENT_INFLATE`** — when `True`, renditions larger than the original are discarded.

### Per-instance override

A single Media can opt into a custom rendition set via the `renditions_config` field (JSON list, same schema as the global `VARIANTS`). Set it to `null` or an empty list to fall back to the global config.

```python
media = Media.objects.get(pk=1)
media.renditions_config = [
    {"name": "tiny", "width": 100, "format": "webp"},
    {"name": "square", "width": 600, "format": "webp"},
]
media.save()
media.regenerate_renditions()
```

### API response shape

`GET /api/camomilla/media/<id>/` now returns two extra fields, `renditions` and `srcset`:

```json
{
    "id": 6,
    "file": "http://mydomain.it/media/sample-image.jpg",
    "thumbnail": "http://mydomain.it/media/thumbnails/sample-image_thumb.jpg",
    "mime_type": "image/jpeg",
    "image_props": {"mode": "RGB", "width": 1980, "format": "JPEG", "height": 1319},
    "renditions": {
        "sm-webp": {
            "url": "http://mydomain.it/media/renditions/sample-image/sm-webp.webp",
            "width": 400, "height": 267, "format": "webp", "size": 18432
        },
        "md-webp": {"url": "...", "width": 800, "height": 533, "format": "webp", "size": 52111},
        "lg-webp": {"url": "...", "width": 1600, "height": 1066, "format": "webp", "size": 180032}
    },
    "srcset": {
        "webp":     "http://.../sm-webp.webp 400w, http://.../md-webp.webp 800w, http://.../lg-webp.webp 1600w",
        "avif":     "http://.../sm-avif.avif 400w, ...",
        "original": "http://.../sm-original.jpg 400w, ..."
    },
    "renditions_config": null
}
```

- **`renditions`** — map keyed by variant name. Each entry has a fully qualified `url`, plus `width`, `height`, `format`, and `size` in bytes. The internal storage `path` is omitted from API output.
- **`srcset`** — convenience map keyed by format, with values already formatted as `"url WIDTHw, url WIDTHw, ..."`. Drop the string straight into a `<source srcset>` attribute.

### Using renditions in a frontend

Build a `<picture>` tag directly from the `srcset` payload:

```html
<picture>
  <source type="image/avif" srcset="{media.srcset.avif}" sizes="(min-width: 1024px) 1600px, 100vw">
  <source type="image/webp" srcset="{media.srcset.webp}" sizes="(min-width: 1024px) 1600px, 100vw">
  <img src="{media.file}" srcset="{media.srcset.original}" alt="{media.alt_text}" loading="lazy">
</picture>
```

If you use Astro, the [Astro Camomilla Integration](../Use%20Astro%20Integration/) ships a ready-made `<CamomillaPicture>` component that consumes this shape directly.

### Regeneration endpoint

Force-regenerate all renditions for a single Media (useful after changing `renditions_config` or after bulk-editing the global `VARIANTS`):

__URL:__ `/api/camomilla/media/<media_id>/regenerate-renditions/` __METHOD:__ `POST`

The response is the freshly re-serialized Media payload.

To regenerate renditions for **every** image Media at once (e.g. after changing the global `VARIANTS`), use the management command:

```bash
python manage.py regenerate_renditions
```

### Template tags

For server-rendered Django templates, `camomilla` ships a `media_extras` library:

```django
{% load media_extras %}

{# Single srcset string #}
<img src="{{ media.file.url }}"
     srcset="{{ media|srcset:'webp' }}"
     sizes="(min-width: 1024px) 1600px, 100vw"
     alt="{{ media.alt_text }}">

{# Full <picture> element #}
{% media_picture media alt="Hero image" sizes="(min-width: 1024px) 1600px, 100vw" class="hero-img" loading="lazy" %}

{# Single rendition URL #}
<img src="{% media_srcset_url media 'md-webp' %}">
```

- **`|srcset:'<format>'`** — filter returning a comma-joined `srcset` string for the given format. Empty string on non-images.
- **`{% media_picture %}`** — renders a full `<picture>` with AVIF/WebP sources + fallback `<img>`. Extra kwargs (`class`, `loading`, `decoding`, `width`, `height`, …) pass through to the `<img>`. Degrades to a bare `<img>` when no renditions exist.
- **`{% media_srcset_url %}`** — returns a single rendition's URL by name.


## 🗂️ Media API

The media model has its own api methods to upload file.

::: warning Beware!
Remember to add camomilla api url to your `urlpatterns`. You can find more info [here](../Use%20API/).
:::

### Upload new media

__URL:__ `/api/camomilla/media` __METHOD:__ `POST` __MODE:__ `MultipartFormData`


__PAYLOAD:__
```
alt_text: Text
title: Text
description: Text
file: Multipart File
folder: Folder id
```

### Update existing media

__URL:__ `/api/camomilla/media/<media_id>` __METHOD:__ `PUT | PATCH` __MODE:__ `MultipartFormData`


__PAYLOAD:__
```
alt_text: Text
title: Text
description: Text
file: Multipart File
folder: Folder id
```
### Get media detail

__URL:__ `/api/camomilla/media/<media_id>` __METHOD:__ `GET` 

__Response:__
```json
{
    "id": 6,
    "links": [],
    "is_image": true,
    "alt_text": null,
    "title": null,
    "description": null,
    "file": "http://mydomain.it/media/sample-image.jpg",
    "thumbnail": "http://mydomain.it/media/thumbnails/sample-image_thumb.jpg",
    "created": "2023-07-24T13:47:26.986873Z",
    "size": 680313,
    "mime_type": "image/jpeg",
    "image_props": {
        "mode": "RGB",
        "width": 1980,
        "format": "JPEG",
        "height": 1319
    },
    "renditions": {
        "sm-webp": {"url": "...", "width": 400, "height": 267, "format": "webp", "size": 18432}
    },
    "srcset": {
        "webp": "http://.../sm-webp.webp 400w, http://.../md-webp.webp 800w, http://.../lg-webp.webp 1600w"
    },
    "renditions_config": null,
    "folder": null
}
```

See [Responsive Renditions](#-responsive-renditions-srcset) above for the full schema and configuration.

### Navigate media folders

To navigate media you need to navigate folder structure.
In the main url you will get all media and all folders without a parent folder (root elements).

__URL:__ `/api/camomilla/media-folder` __METHOD:__ `GET`

__Response:__
```json
{
    "folders": [
        {
            "id": 1,
            "title": "Folder 1",
            "slug": "folder-1",
            "creation_date": "2023-07-31T15:17:37.612115Z",
            "last_modified": "2023-07-31T15:17:37.612173Z",
            "path": "/folder-1",
            "updir": null
        }
    ],
    "media": {
        "items": [
            {
                "id": 6,
                "is_image": true,
                "alt_text": null,
                "title": null,
                "description": null,
                "file": "http://mydomain.com/media/sample-image.jpg",
                "thumbnail": "http://mydomain.com/media/thumbnails/sample-image_thumb.jpg",
                "created": "2023-07-24T13:47:26.986873Z",
                "size": 680313,
                "mime_type": "image/jpeg",
                "image_props": {
                    "mode": "RGB",
                    "width": 1980,
                    "format": "JPEG",
                    "height": 1319
                },
                "folder": null,
            }
        ],
        "paginator": {
            "count": 1,
            "page": 1,
            "has_next": false,
            "has_previous": false,
            "pages": 1,
            "page_size": 18
        }
    },
    "parent_folder": {
        "title": "",
        "path": "",
        "updir": null
    }
}
```

To navigate a subfolder just add its id to the url path:

__URL:__ `/api/camomilla/media-folder/<folder_id>` __METHOD:__ `GET`

The media endpoint response is always paginated. The pagination is made only for media elements. For subfolder you will get always all subfolder in a folder.







