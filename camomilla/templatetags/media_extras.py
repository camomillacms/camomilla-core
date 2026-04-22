from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


def _renditions(media):
    renditions = getattr(media, "renditions", None) or {}
    if not isinstance(renditions, dict):
        return {}
    return renditions


def _by_format(media):
    grouped = {}
    for entry in _renditions(media).values():
        if not isinstance(entry, dict):
            continue
        fmt = entry.get("format")
        width = entry.get("width")
        url = entry.get("url")
        if not fmt or not width or not url:
            continue
        grouped.setdefault(fmt, []).append((width, url))
    for fmt in grouped:
        grouped[fmt].sort(key=lambda x: x[0])
    return grouped


@register.filter(name="srcset")
def media_srcset(media, format_name="webp"):
    """
    Build a `srcset` string for the given format from a Media instance.

    URLs are whatever is stored on `media.renditions[name].url` — typically
    storage-relative. For same-origin server-side rendering this is fine;
    cross-origin callers should use the DRF serializer's absolute URLs.
    """
    if not media:
        return ""
    grouped = _by_format(media)
    items = grouped.get(format_name)
    if not items:
        return ""
    return ", ".join("{} {}w".format(url, width) for width, url in items)


@register.simple_tag(name="media_srcset_url")
def media_srcset_url(media, rendition_name):
    if not media:
        return ""
    entry = _renditions(media).get(rendition_name)
    if not isinstance(entry, dict):
        return ""
    return entry.get("url", "")


def _fallback_src(media, grouped, fallback_format):
    items = grouped.get(fallback_format) or grouped.get("original")
    if items:
        return items[-1][1]
    for fmt_items in grouped.values():
        if fmt_items:
            return fmt_items[-1][1]
    if getattr(media, "file", None):
        try:
            return media.file.url
        except Exception:
            return ""
    return ""


@register.simple_tag(name="media_picture")
def media_picture(
    media,
    alt=None,
    sizes=None,
    formats=None,
    fallback="original",
    **attrs,
):
    if not media:
        return ""
    formats = formats or ["avif", "webp"]
    grouped = _by_format(media)
    alt_text = alt if alt is not None else (getattr(media, "alt_text", "") or "")

    img_src = _fallback_src(media, grouped, fallback)

    if not grouped:
        img_attrs = {"src": img_src, "alt": alt_text, **attrs}
        return mark_safe(
            "<img {}>".format(
                " ".join(
                    '{}="{}"'.format(k, escape(v)) for k, v in img_attrs.items() if v is not None
                )
            )
        )

    source_mime = {
        "avif": "image/avif",
        "webp": "image/webp",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    sources = []
    for fmt in formats:
        items = grouped.get(fmt)
        if not items:
            continue
        srcset = ", ".join("{} {}w".format(url, w) for w, url in items)
        parts = [
            'type="{}"'.format(source_mime.get(fmt, "image/" + fmt)),
            'srcset="{}"'.format(escape(srcset)),
        ]
        if sizes:
            parts.append('sizes="{}"'.format(escape(sizes)))
        sources.append("<source {}>".format(" ".join(parts)))

    img_attrs = {"src": img_src, "alt": alt_text}
    if sizes:
        img_attrs["sizes"] = sizes
    img_attrs.update(attrs)
    img_tag = "<img {}>".format(
        " ".join(
            '{}="{}"'.format(k, escape(v)) for k, v in img_attrs.items() if v is not None
        )
    )

    return mark_safe("<picture>{sources}{img}</picture>".format(
        sources="".join(sources),
        img=img_tag,
    ))
