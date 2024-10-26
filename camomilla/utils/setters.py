from typing import Sequence
from .getters import pointed_getter


def set_key(data, key, val):
    if isinstance(data, Sequence):
        key = int(key)
        if key < len(data):
            data[key] = val
        else:
            data.append(val)
        return data
    elif isinstance(data, dict):
        data[key] = val
    else:
        setattr(data, key, val)
    return data


def get_key(data, key, default):
    if isinstance(data, Sequence):
        try:
            return data[int(key)]
        except IndexError:
            return default
    return pointed_getter(data, key, default)


def pointed_setter(data, path, value):
    path = path.split(".")
    key = path.pop(0)
    if not len(path):
        return set_key(data, key, value)
    default = [] if path[0].isdigit() else {}
    return set_key(
        data, key, pointed_setter(get_key(data, key, default), ".".join(path), value)
    )
