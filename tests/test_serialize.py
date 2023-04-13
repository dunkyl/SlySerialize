from enum import Enum
from dataclasses import dataclass, asdict
from SlySerialize.de import to_json
from SlySerialize import JsonType


def test_to_json_simple():
    for x in (None, 1, 2.5, "hi", True):
        assert x == to_json(x)

def test_to_json_seq():

    list_xs = [1, 2, 3]
    assert list_xs == to_json(list_xs)

    assert list_xs == to_json({1, 2, 3})

    assert list_xs == to_json((1, 2, 3))

def test_to_json_dict():

    dict_xs = {"a": 1, "b": 2, "c": 3}
    assert dict_xs == to_json(dict_xs)

def test_to_json_enum():

    class Test(Enum):
        A = 1
        B = 2

    x = Test.A
    assert x.value == to_json(x)

def test_to_json_dataclass():

    @dataclass
    class X:
        a: int
        b: str
        c: JsonType

    x = X(1, "hi", {'x': 1, 'y': {}, 'z': [None, 2.5]})
    assert asdict(x) == to_json(x)

def test_to_json_to_json():

    class X:
        value: int

        def __init__(self, value: int):
            self.value = value
        
        def to_json(self):
            return self.value
        
    a = X(1)

    assert a.value == to_json(a)
