"""
Runtime Pydantic model compiler for MetaType definitions.

A MetaType stores a list of MetaTypeFieldDef rows. At runtime we walk that
list and build a structured.pydantic BaseModel subclass that mirrors the
declared shape. The resulting class can be:

- handed to ``structured.widget.fields.StructuredJSONFormField`` so the admin
  renders the JSON-schema editor for it,
- used to validate / serialize MetaInstance.data,
- introspected (``json_schema()``) by the REST API for frontends.

Compiled models are cached per ``(meta_type_id, compiled_at)`` so that saves
on the MetaType invalidate the cache automatically.
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Type

from django.apps import apps
from pydantic import Field, create_model
from structured.pydantic.models import BaseModel

from .schema_builder import MetaFieldKind, MetaTypeFieldDef


_cache: Dict[Tuple[int, str], Type[BaseModel]] = {}


def clear_cache(meta_type_id: Optional[int] = None) -> None:
    if meta_type_id is None:
        _cache.clear()
        return
    for key in [k for k in _cache if k[0] == meta_type_id]:
        _cache.pop(key, None)


_PRIMITIVE_TYPES = {
    MetaFieldKind.string: str,
    MetaFieldKind.text: str,
    MetaFieldKind.integer: int,
    MetaFieldKind.number: float,
    MetaFieldKind.boolean: bool,
    MetaFieldKind.date: date,
    MetaFieldKind.datetime: datetime,
}


def _resolve_ref_model(target_model: str):
    if not target_model or "." not in target_model:
        raise ValueError(
            f"MetaType ref field requires target_model as 'app.Model', got {target_model!r}"
        )
    app_label, model_name = target_model.split(".", 1)
    return apps.get_model(app_label, model_name)


def _media_model():
    return apps.get_model("camomilla", "Media")


def _field_type(field_def: MetaTypeFieldDef, model_name_hint: str):
    kind = field_def.kind
    if kind in _PRIMITIVE_TYPES:
        return _PRIMITIVE_TYPES[kind]
    if kind == MetaFieldKind.media:
        return _media_model()
    if kind == MetaFieldKind.ref:
        return _resolve_ref_model(field_def.target_model)
    if kind == MetaFieldKind.group:
        return _build_group_model(
            field_def.children, f"{model_name_hint}__{field_def.name}"
        )
    if kind == MetaFieldKind.list:
        item_model = _build_group_model(
            field_def.children, f"{model_name_hint}__{field_def.name}_item"
        )
        return List[item_model]
    raise ValueError(f"Unknown MetaType field kind: {kind!r}")


def _build_group_model(
    fields: List[MetaTypeFieldDef], model_name: str
) -> Type[BaseModel]:
    field_specs: dict = {}
    for fdef in fields:
        if isinstance(fdef, dict):
            fdef = MetaTypeFieldDef.model_validate(fdef)
        py_type = _field_type(fdef, model_name)
        if fdef.translated:
            py_type = Dict[str, py_type]
        if fdef.required:
            default = Field(...)
        else:
            py_type = Optional[py_type]
            default = Field(default=None)
        field_specs[fdef.name] = (py_type, default)

    return create_model(  # type: ignore[call-overload]
        model_name,
        __base__=BaseModel,
        **field_specs,
    )


def build_pydantic_model(meta_type) -> Type[BaseModel]:
    """
    Build (or fetch from cache) the runtime Pydantic model for a MetaType.
    """
    cache_key = (meta_type.pk, str(meta_type.compiled_at or ""))
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    fields = list(meta_type.schema or [])
    model_cls = _build_group_model(fields, f"MetaType_{meta_type.pk}_{meta_type.key}")
    _cache[cache_key] = model_cls
    return model_cls


def get_json_schema(meta_type) -> dict:
    return build_pydantic_model(meta_type).model_json_schema()
