from camomilla.utils.normalization import dict_merge

def test_dict_merge_simple():
    a = {'x': 1}
    b = {'y': 2}
    result = dict_merge(a.copy(), b)
    assert result == {'x': 1, 'y': 2}

def test_dict_merge_overwrite():
    a = {'x': 1}
    b = {'x': 2}
    result = dict_merge(a.copy(), b)
    assert result == {'x': 2}

def test_dict_merge_nested():
    a = {'x': {'y': 1}}
    b = {'x': {'z': 2}}
    result = dict_merge(a.copy(), b)
    assert result == {'x': {'y': 1, 'z': 2}}

def test_dict_merge_nested_overwrite():
    a = {'x': {'y': 1}}
    b = {'x': {'y': 2}}
    result = dict_merge(a.copy(), b)
    assert result == {'x': {'y': 2}}

def test_dict_merge_empty():
    a = {}
    b = {'foo': 1}
    result = dict_merge(a.copy(), b)
    assert result == {'foo': 1}

def test_dict_merge_both_empty():
    a = {}
    b = {}
    result = dict_merge(a.copy(), b)
    assert result == {}
