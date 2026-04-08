from enum import Enum
from typing import Annotated, List, Optional
from pydantic import ConfigDict, Field
from structured.pydantic.models import BaseModel
from structured.pydantic.conditionals import When, conditional_schema


def _target_model_enum(schema: dict) -> None:
    """
    Inject an enum of all installed Django models into the JSON schema.

    For Optional[str] Pydantic emits ``anyOf: [{type: string}, {type: null}]``.
    A sibling ``enum`` at that level is ignored by most JSON Schema editors, so
    we place the enum inside the string branch instead.
    """
    from django.apps import apps

    enum = sorted(f"{m._meta.app_label}.{m.__name__}" for m in apps.get_models())
    for branch in schema.get("anyOf", []):
        if branch.get("type") == "string":
            branch["enum"] = enum
            return
    # Fallback for non-optional usage
    schema["enum"] = enum


class MetaFieldKind(str, Enum):
    string = "string"
    text = "text"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    media = "media"
    ref = "ref"
    group = "group"
    list = "list"


class MetaTypeFieldDef(BaseModel):
    """
    Describes a single field declared by an editor on a MetaType.
    The full ``MetaType.schema`` is a list of these (possibly nested via children).

    Conditional logic:
    - ``target_model`` is shown (and required) only when ``kind == "ref"``.
    - ``children`` is shown only when ``kind`` is ``"group"`` or ``"list"``.
    """

    name: str
    label: str = ""
    kind: MetaFieldKind = MetaFieldKind.string
    required: bool = False
    translated: bool = False
    # Shown only for kind=ref — select rendered from all installed Django models
    target_model: Annotated[Optional[str], Field(default=None, json_schema_extra=_target_model_enum)] = None
    # Shown only for kind=group / kind=list
    children: List["MetaTypeFieldDef"] = Field(default_factory=list)
    # Free-form options (e.g. choices, max_length). Forwarded as Field metadata.
    options: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra=conditional_schema(
            When(
                "kind",
                equals="ref",
                controls=["target_model"],
                then={"required": ["target_model"]},
            ),
            When(
                "kind",
                in_=["group", "list"],
                controls=["children"],
            ),
        )
    )


MetaTypeFieldDef.model_rebuild()
