from django.db import connections
from datetime import datetime
from django.utils import dateparse

_mysql_datetime_patched = False  # module level flag to avoid double patching


def monkey_patch_mysql_datetime():  # pragma: no cover - environment/driver specific
    """Normalize MySQL DATETIME values that arrive as strings.

    In some environments (notably with certain PyMySQL versions / settings)
    MySQL returns DATETIME columns as raw strings. Django's MySQL backend then
    hands those straight to its timezone utilities expecting a datetime.
    That raises AttributeError on value.utcoffset(). We monkeypatch the
    backend converter once to coerce any string into a datetime before the
    original logic runs.
    """
    global _mysql_datetime_patched
    if _mysql_datetime_patched:
        return
    try:
        for alias in connections:
            conn = connections[alias]
            if conn.vendor != "mysql":
                continue
            ops = conn.ops
            original = ops.convert_datetimefield_value

            def _patched_convert(value, expression, connection, _orig=original):
                if isinstance(value, str):
                    dt = dateparse.parse_datetime(value.replace(" ", "T", 1)) or None
                    if dt is None:
                        try:
                            dt = datetime.fromisoformat(value)
                        except Exception:
                            dt = None
                    if dt is not None:
                        value = dt
                return _orig(value, expression, connection)

            ops.convert_datetimefield_value = _patched_convert  # type: ignore[attr-defined]
            _mysql_datetime_patched = True
    except Exception:
        # Fail silently; if conversion still fails tests will reveal it.
        pass
