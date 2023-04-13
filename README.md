# Sly Serialize for Python

Convert JSON-like data structures into nice Python objects.

Key features:

- Common, built-in types like `set` and `tuple`
- Generic dataclasses and nested generics
- Type aliases
- Union types
- Asynchronous custom deserialization
- Deserialization dependencies

## Basic usage

Call `convert_from_json` with a target type, with generic arguments, and some json data, such as returned from `json.loads`. Generic arguments are optional, but if you don't provide them, you'll get a `TypeError` if the target type requires them to be concrete. See the final line in the following example:

```py
from typing import Generic, TypeVar, TypeAlias
from dataclasses import dataclass
from SlySerialize import convert_from_json

ListOfInts: TypeAlias = list[int]
T = TypeVar("T")

@dataclass
class MyClass(Generic[T]):
    aliased: ListOfInts
    generic: T
    builtin: tuple[float, set[str]]
    union: dict[str, T] | None
    delayed: 'MyClass[T] | None'

my_obj = MyClass[int]([1, 2, 3], 42, (3.1, {"a"}), None, None)

# asdict(my_obj)
serialized = {
    "aliased": [1, 2, 3],   "generic": 42,
    "union":   None,        "delayed": None
    "builtin": [3.1, ["a"]],
}

assert my_obj == convert_from_json(MyClass[int], serialized)
```

## Notes

Type variables or mutually recursive types must be declared in the global scope if used in a delayed annotation.

Not all types are guarunteed to round-trip. For a simple example, `list` and `set` are both serialized as a JSON array, so if there is a union `list[T|None] | set[U|None]`, and a value `{ None }`, then the first case, `list[T]`, will be selected during deserialization.
