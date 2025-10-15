from camomilla.utils.getters import safe_getter, pointed_getter, find_and_replace_dict


def test_safe_getter_dict():
    d = {"a": 1}
    assert safe_getter(d, "a") == 1
    assert safe_getter(d, "b", 42) == 42


def test_safe_getter_object():
    class Dummy:
        foo = "bar"

    obj = Dummy()
    assert safe_getter(obj, "foo") == "bar"
    assert safe_getter(obj, "baz", 99) == 99


def test_pointed_getter_dict():
    d = {"a": {"b": {"c": 5}}}
    assert pointed_getter(d, "a.b.c") == 5
    assert pointed_getter(d, "a.b.x", "nope") == "nope"


def test_pointed_getter_object():
    class Dummy:
        pass

    obj = Dummy()
    obj.child = Dummy()
    obj.child.value = 123
    assert pointed_getter(obj, "child.value") == 123
    assert pointed_getter(obj, "child.missing", "default") == "default"


def test_find_and_replace_dict_simple():
    d = {"a": 1, "b": 2}

    def pred(key, value):
        return value * 2

    result = find_and_replace_dict(d, pred)
    assert result == {"a": 2, "b": 4}


def test_find_and_replace_dict_nested():
    d = {"a": {"b": 2}, "c": 3}

    def pred(key, value):
        return value if not isinstance(value, int) else value + 1

    result = find_and_replace_dict(d, pred)
    assert result == {"a": {"b": 3}, "c": 4}
