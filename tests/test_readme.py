from typing import Generic, TypeVar, TypeAlias
from dataclasses import dataclass
from SlySerialize import from_json

ListOfInts: TypeAlias = list[int]
T = TypeVar("T")

def test_readme():
    
    @dataclass
    class MyClass(Generic[T]):
        aliased: ListOfInts
        generic: T
        builtin: tuple[float, list[str]]
        union: dict[str, T] | None
        delayed: 'MyClass[T] | None'

    my_obj = MyClass[int]([1, 2, 3], 42, (3.1, ["a"]), None, None)

    # dataclasses.asdict(my_obj)
    serialized = {
        "aliased": [1, 2, 3],   "generic": 42,
        "union":   None,        "delayed": None,
        "builtin": [3.1, ["a"]],
    }

    assert my_obj == from_json(MyClass[int], serialized)