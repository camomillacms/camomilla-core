from django import template
from django.utils.safestring import mark_safe
from django.forms.models import model_to_dict
from structured.pydantic.models import BaseModel
import json
import re
import html
from datetime import datetime

register = template.Library()


def custom_json_serializer(obj):
    """Serialize custom objects to JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def pretty_dict(data, indent_level=0):
    """
    Recursive function to format a dictionary into a pretty string.
    Args:
        data (dict): The dictionary to format.
        indent_level (int): The current indentation level.
    Returns:
        str: A pretty-printed string representation of the dictionary.
    """
    indent = "  " * indent_level
    result = []

    for key, value in data.items():

        if isinstance(value, dict):
            result.append(f"{indent}'{key}': {{")
            result.append(pretty_dict(value, indent_level + 1))
            result.append(f"{indent}}},")

        elif isinstance(value, list):
            result.append(f"{indent}'{key}': [")
            for item in value:
                if isinstance(item, dict):
                    result.append(pretty_dict(item, indent_level + 1))
                else:
                    result.append(
                        f"{indent}  {json.dumps(item, default=custom_json_serializer)},"
                    )
            result.append(f"{indent}],")

        else:
            result.append(
                f"{indent}'{key}': {json.dumps(value, default=custom_json_serializer)},"
            )

    return "\n".join(result).rstrip(",")


@register.filter
def to_pretty_dict(instance):
    data = model_to_dict(instance)

    for key, value in data.items():
        if isinstance(value, BaseModel):
            data[key] = value.model_dump()

    formatted_dict = "{\n" + pretty_dict(data, indent_level=1) + "\n}"

    escaped = html.escape(formatted_dict)

    # This to highlight the keys in the JSON
    highlighted = re.sub(
        r"(&#x27;)([^&#]+?)(&#x27;):",
        r"<span style='color:#df3079'>'\2'</span>:",
        escaped,
    )

    return mark_safe(f"<pre>{highlighted}</pre>")
