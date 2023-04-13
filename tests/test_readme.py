from typing import Generic, TypeVar, TypeAlias
from dataclasses import dataclass
from SlySerialize import convert_from_json

ListOfInts: TypeAlias = list[int]
T = TypeVar("T")

def test_readme():
    
    @dataclass
    class MyClass(Generic[T]):
        aliased: ListOfInts
        generic: T
        builtin: tuple[float, set[str]]
        union: dict[str, T] | None
        delayed: 'MyClass[T] | None'

    my_obj = MyClass[int]([1, 2, 3], 42, (3.14, {"a", "b", "c"}), None, None)

    # asdict(my_obj)
    serialized = {
        "aliased": [1, 2, 3],
        "generic": 42,
        "builtin": [3.14, ["a", "b", "c"]],
        "union": None,
        "delayed": None
    }

    assert my_obj == convert_from_json(MyClass[int], serialized)