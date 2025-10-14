import json

from django.db import connection

from django.db.models import JSONField as DjangoJSONField
from django.db import models


if connection.vendor == "sqlite":  # noqa: C901

    class JSONField(models.Field):
        def db_type(self, connection):
            return "text"

        def from_db_value(self, value, expression, connection):
            if value is not None:
                return self.to_python(value)
            return value

        def to_python(self, value):
            if value is not None:
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    return value
            return value

        def get_prep_value(self, value):
            if value is not None:
                return str(json.dumps(value))
            return value

        def value_to_string(self, obj):
            return self.value_from_object(obj)

else:

    class JSONField(DjangoJSONField):
        pass


__all__ = [JSONField]
