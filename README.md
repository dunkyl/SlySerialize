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

ListOfIntegers: TypeAlias = list[int]
T = TypeVar("T")

@dataclass
class MyClass(Generic[T]):
    aliased: ListOfIntegers
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

assert my_obj == convert_from_json(MyClass[int], serialized)
```

## Notes

Type variables or mutually recursive types must be declared in the global scope if used in a delayed annotation.

`SlySerialize.JsonType` is an alias for the return type of `json.loads` (Python standard library), it represents the native JSON types.

Not all types are guaranteed to round-trip. For a simple example, `list` and `set` are both serialized as a JSON array, so if there is a union `list | set`, and an empty value, then the first case, `list`, will be selected during deserialization. Other examples would include `dict` and classes, or classes that have the same member names.

If the type is not supported, or if the representation was different than what was expected, a `TypeError` will be raised.

`dataclasses.asdict` only supports serializing dataclasses, `JsonType`, `tuple`, and lists, tuples, or dicts of these. There will not be an error, but, the return type is *not* `JsonType`. Other types will be passed through unaffected. If you want to serialize a dataclass with a member that is not one of these types, you may want to implement your own serialization.

## Default Representations

The following types are supported by default:

- `NoneType`, `bool`, `int`, `float`, and `str` as themselves
- `list` and `dict` as arrays and maps, with or without their generic arguments
    - `dict` is only supported if the key type is `str`
    - The default value type used with no arguments is `JsonType`
- `tuple` and `set` as an array
- Dataclasses as maps
- Union types as whichever case the value would otherwise be represented as
- Generic types are substituted for their concrete type. If the type is not available, a `ValueError` is raised.
- The covariant versions of `list` and `map`, `collections.abc.Sequence` and `collections.abc.Mapping`, are also supported.
    - Consequently, `JsonType` is a valid type to deserialize to. If you want to do nothing to a member during deserialization, use `JsonType` as the type.

