from typing import Generic, TypeVar, TypeAlias
from dataclasses import dataclass
from SlySerialize import from_json, to_json, JsonType

ListOfInts: TypeAlias = list[int]
T = TypeVar("T")

@dataclass
class MyClass(Generic[T]):
    aliased: ListOfInts
    generic: T
    builtin: tuple[float, list[str]]
    union: dict[str, T] | None
    delayed: 'MyClass[T] | None'

def test_in_one_line():

    myThing = MyClass[int]([1, 2, 3], 42, (3.1, ["a"]), None, None)

    assert myThing == from_json(MyClass[int], to_json(myThing))

def test_readme():

    my_obj = MyClass[int]([1, 2, 3], 42, (3.1, ["a"]), None, None)

    # dataclasses.asdict(my_obj)
    serialized: JsonType = {
        "aliased": [1, 2, 3],   "generic": 42,
        "union":   None,        "delayed": None,
        "builtin": [3.1, ["a"]],
    }

    assert my_obj == from_json(MyClass[int], serialized)

    # ...
    
    from SlySerialize import to_json

    assert serialized == to_json(my_obj)