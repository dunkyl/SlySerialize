# Sly Serialize for Python

Convert JSON-like data structures into nice Python objects.

Key features:

- Common, built-in types like `set`, `tuple` and `Enum`
- Generic dataclasses and nested generics
- Type aliases
- Union types
- Recursive types and delayed annotations
- Custom deserialization
- Asynchronous custom deserialization
- Zero dependencies

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

## Should I use this?

The goal of this library is to handle deserialization cases for strongly typed dataclass and custom types, and to do so with as little code as possible.

If you only want fast and customizable *serialization*, but maybe not deserialization, you should use a library like [orjson](https://pypi.org/project/orjson/).

If you are using JSON-like types already, without generics or some other specific feature, there are also other libraries that will deserialize faster.

The serialization format for JSON in this library also prefers succinctness at the cost of certain edge cases related to overlapping type representations. See the [Default Representations](#default-representations) section for more details.

## Notes

Type variables or mutually recursive types must be declared in the global scope if used in a delayed annotation.

`SlySerialize.JsonType` is an alias for the return type of `json.loads` (Python standard library), it represents the native JSON types.

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
- Enum types of `str` or `int` as their value
- Union types as whichever case the value would otherwise be represented as
- Generic types are substituted for their concrete type. If the type is not available, a `ValueError` is raised.
- The covariant versions of `list` and `map`, `collections.abc.Sequence` and `collections.abc.Mapping`, are also supported.
    - Consequently, `JsonType` is a valid type to deserialize to. If you want to do nothing to a member during deserialization, use `JsonType` as the type.

Not all types are guaranteed to round-trip. For a simple example, `list` and `set` are both serialized as a JSON array, so if there is a union `list | set`, and an empty value, then the first case, `list`, will be selected during deserialization. Other examples would include `dict` and classes, or classes that have the same member names.

## Serialization

Implementations for serialization is provided. Some type loaders that are needed for deserialization do not have a corresponding serializer, such as `TypeVar` and `TypeAlias`, since  it would be unusual for an instance value to be these types.

```py
# ...
from SlySerialize import to_json

assert serialized == to_json(my_obj)

```

In most cases, `to_json` should be the inverse of `from_json`.

## Custom Converters

Custom converters can be created for any type. Subclass `Loader` or `Unloader`, or `Converter` for both. These have a generic argument for the domain type that they serialize to or from. For JSON, this is `JsonType`. Some of the loaders implemented by this library do not require a specific domain, so they may be combined with custom loaders for other domain types.

Loaders must implement the following two methods:

```py
    def can_load(self, cls: type) -> bool: ...

    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[MyType]) -> MyType: ...
```

And unloaders must implement:

```py
    def can_unload(self, cls: type) -> bool: ...

    def ser(self, ctx: SerCtx[Domain], obj: MyType) -> Domain: ...
```

Where `DesCtx` and `SerCtx` are used to recursively call the top level converter being used.

In most cases can_unload can be implemented in terms of can_load.

The converters implemented by this library are available in `SlySerialize.COMMON_CONVERTERS`, which is a `ConverterCollection` that implements `Converter[JsonType]`.

To use a custom converter, pass any `Converter`  to `from_json` or `to_json`:

```py
# ...

custom_converter = COMMON_CONVERTERS.with_(MyConverter())

thing = from_json(MyClass[int], serialized, custom_converter)
```

It is not strictly necessary to use a `ConverterCollection`.

## Async Loaders

Async loaders are supported. They must implement the following methods:

```py
    def can_load(self, cls: type) -> bool: ...

    async def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[MyType]) -> MyType: ...
```

When a loader is async or part of a `ConverterCollection`, then `from_json_async` must be used instead of `from_json` or an error will be raised. There is no async version of `to_json` nor any async version of `Unloader`. It is OK to pass a `ConverterCollection` with async loaders to `to_json`, since it will only access converters that implement `Loader`.

