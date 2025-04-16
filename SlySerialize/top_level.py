'Functions and converters for using SlySerialize.'
from .abc import Converter, Loader
from .converters import *
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

_common: list[Converter[JsonType]] = [
    JsonScalarConverter(),
    ListOrSetConverter(),
    TupleConverter(),
    DictStrConverter(),
    ToFromJsonConverter(),
    EnumConverter(),
    DatetimeConverter(),
]

# Loaders for types that have no concrete instances
_special_loaders: list[Loader[JsonType]] = [
    TypeVarLoader(),
    UnionLoader(),
    DelayedAnnotationLoader(),
    CollectionsAbcLoader(),
    TypeAliasLoader()
]

COMMON_CONVERTER = ConverterCollection(
    *_common,
    DataclassConverter(False),
    loaders=[*_special_loaders]
)

COMMON_CONVERTER_UNSTRICT = ConverterCollection(
    *_common,
    DataclassConverter(True),
    loaders=[*_special_loaders]
)

def from_json[T](cls: TypeForm[T], value: JsonType, \
                      loader: Loader[JsonType] | None = None,
                      allow_extra_keys: bool=False) -> T:
    '''Converts a value from JSON to a type T.

    If not specified, uses the default converter.'''
    if loader is None:
        if allow_extra_keys:
            loader = COMMON_CONVERTER_UNSTRICT
        else:
            loader = COMMON_CONVERTER
    context = LoadingContext(loader, only_sync=True)
    context.parent_type = cls # type: ignore - TODO find a good type for parent_type. see other todos.
    return context.des(value, cls)

async def from_json_async[T](cls: TypeForm[T], value: JsonType,
                            loader: Loader[JsonType] | None = None,
                            allow_extra_keys: bool=False) -> T:
    '''Converts a value from JSON to a type T with support for async converters.'''
    if loader is None:
        if allow_extra_keys:
            loader = COMMON_CONVERTER_UNSTRICT
        else:
            loader = COMMON_CONVERTER
    partial = LoadingContext(loader, only_sync=False).des(value, cls)
    return await _recursive_await(partial) # type: ignore - _recursive_await may need a generalization

def to_json(value: Any, converter: Converter[JsonType]|None=None) -> JsonType:
    '''Converts a value to JSON.'''
    if converter is None:
        converter = COMMON_CONVERTER
    context = UnloadingContext(converter)
    return context.ser(value)

async def _recursive_await(value: asyncio.Future[Any] \
            | list[Any] | dict[str, Any] | set[Any] \
            | tuple[Any, ...] | DataclassInstance
        ) -> Any:
    '''Await a value, or all values in it'''
    if inspect.isawaitable(value):
        return await value
    if isinstance(value, list):
        return [await _recursive_await(v) for v in value]
    elif isinstance(value, dict):
        return {k: await _recursive_await(v) for k, v in value.items()}
    elif isinstance(value, set):
        return {await _recursive_await(v) for v in value}
    elif isinstance(value, tuple):
        vals = [(await _recursive_await(v)) for v in value]
        return tuple(*vals)
    elif is_dataclass(value):
        return type(value)(**{f.name: await _recursive_await(getattr(value, f.name)) for f in fields(value)})
    else:
        return value