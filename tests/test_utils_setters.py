import pytest
from camomilla.utils import setters

def test_set_key_dict():
    d = {'a': 1}
    result = setters.set_key(d, 'b', 2)
    assert result['b'] == 2
    assert d['b'] == 2

def test_set_key_list():
    l = [1, 2]
    result = setters.set_key(l, 1, 3)
    assert result[1] == 3
    result = setters.set_key(l, 2, 4)
    assert result[2] == 4

def test_set_key_object():
    class Dummy:
        pass
    obj = Dummy()
    setters.set_key(obj, 'foo', 'bar')
    assert obj.foo == 'bar'

def test_get_key_list():
    l = [10, 20]
    assert setters.get_key(l, 1, 'x') == 20
    assert setters.get_key(l, 5, 'x') == 'x'

def test_pointed_setter_dict():
    d = {'a': {'b': 1}}
    setters.pointed_setter(d, 'a.b', 2)
    assert d['a']['b'] == 2

def test_pointed_setter_list():
    l = [[0, 1], [2, 3]]
    setters.pointed_setter(l, '1.1', 99)
    assert l[1][1] == 99

def test_set_key_list_append():
    l = [1]
    # key out of range, should append
    setters.set_key(l, 2, 42)
    assert l == [1, 42]

def test_set_key_invalid_type():
    class Dummy:
        pass
    obj = Dummy()
    # Should set attribute if not dict or list
    setters.set_key(obj, 'bar', 123)
    assert obj.bar == 123

def test_get_key_invalid_index():
    l = [1, 2]
    # Out of range index returns default
    assert setters.get_key(l, 10, 'default') == 'default'

def test_pointed_setter_new_path():
    d = {}
    # Should create nested dicts
    setters.pointed_setter(d, 'foo.bar.baz', 7)
    assert d['foo']['bar']['baz'] == 7
