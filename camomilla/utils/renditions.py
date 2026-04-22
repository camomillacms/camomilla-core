import logging
import os
from io import BytesIO

from PIL import Image

from camomilla import settings

logger = logging.getLogger(__name__)

try:
    import pillow_avif  # noqa: F401

    AVIF_AVAILABLE = True
except ImportError:
    AVIF_AVAILABLE = False

FORMAT_TABLE = {
    "webp": ("WEBP", "webp"),
    "avif": ("AVIF", "avif"),
    "jpeg": ("JPEG", "jpg"),
    "jpg": ("JPEG", "jpg"),
    "png": ("PNG", "png"),
}

PIL_TO_NAME = {
    "WEBP": "webp",
    "AVIF": "avif",
    "JPEG": "jpeg",
    "PNG": "png",
    "GIF": "gif",
}


def resolve_format(rendition_cfg, source_pil_format):
    fmt = (rendition_cfg.get("format") or "original").lower()
    if fmt == "original":
        source_name = PIL_TO_NAME.get(
            (source_pil_format or "JPEG").upper(), "jpeg"
        )
        pil_format, ext = FORMAT_TABLE.get(source_name, ("JPEG", "jpg"))
        save_kwargs = {"optimize": True}
        if pil_format == "JPEG":
            save_kwargs["quality"] = settings.MEDIA_RENDITIONS_JPEG_QUALITY
        return pil_format, ext, save_kwargs, source_name

    if fmt not in FORMAT_TABLE:
        return None, None, None, None

    pil_format, ext = FORMAT_TABLE[fmt]
    save_kwargs = {"optimize": True}
    if pil_format == "JPEG":
        save_kwargs["quality"] = settings.MEDIA_RENDITIONS_JPEG_QUALITY
    elif pil_format == "WEBP":
        save_kwargs["quality"] = settings.MEDIA_RENDITIONS_WEBP_QUALITY
    elif pil_format == "AVIF":
        save_kwargs["quality"] = settings.MEDIA_RENDITIONS_AVIF_QUALITY
    return pil_format, ext, save_kwargs, fmt


def build_rendition_path(original_name, rendition_name, extension, folder):
    stem = os.path.splitext(os.path.basename(original_name))[0]
    return "{folder}/{stem}/{name}.{ext}".format(
        folder=folder.strip("/"),
        stem=stem,
        name=rendition_name,
        ext=extension,
    )


def generate_rendition(pil_image, cfg, source_pil_format, original_size):
    target_width = int(cfg.get("width") or 0)
    if target_width <= 0:
        return None

    if target_width >= pil_image.width:
        return None

    pil_format, ext, save_kwargs, fmt_name = resolve_format(cfg, source_pil_format)
    if pil_format is None:
        return None

    if pil_format == "AVIF" and not AVIF_AVAILABLE:
        return None

    ratio = target_width / pil_image.width
    target_height = max(1, int(round(pil_image.height * ratio)))

    image = pil_image.copy()
    image = image.resize((target_width, target_height), Image.LANCZOS)

    if pil_format in ("JPEG",) and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    tmp = BytesIO()
    try:
        image.save(tmp, pil_format, **save_kwargs)
    except Exception as e:
        logger.error(
            "Error saving rendition %s as %s: %s", cfg.get("name"), pil_format, e
        )
        tmp.close()
        return None

    data = tmp.getvalue()
    tmp.close()

    if (
        settings.MEDIA_RENDITIONS_PREVENT_INFLATE
        and original_size
        and len(data) > original_size
    ):
        return None

    return {
        "bytes": data,
        "width": target_width,
        "height": target_height,
        "format": fmt_name,
        "ext": ext,
        "size": len(data),
    }


def iter_renditions(image_bytes, config):
    image_bytes.seek(0)
    with Image.open(image_bytes) as source:
        source.load()
        source_format = source.format
        original_size = 0
        try:
            image_bytes.seek(0, os.SEEK_END)
            original_size = image_bytes.tell()
            image_bytes.seek(0)
        except Exception:
            original_size = 0

        for cfg in config or []:
            result = generate_rendition(source, cfg, source_format, original_size)
            yield cfg, result
