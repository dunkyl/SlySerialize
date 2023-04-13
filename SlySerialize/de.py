'''
Extended support for deserialization of Python types from JSON
'''
from .converter import Loader, LoaderCollection, DesCtx
from .converters import *
from .asynch import recursive_await

_basic = (
    JsonScalarConverter(),
    ListOrSetLoader(),
    CollectionsAbcLoader(),
    TupleLoader(),
    DictLoader(),
    FromJsonLoader(),
)

COMMON_CONVERTER = LoaderCollection(
    *_basic,
    DataclassLoader(False),
    EnumLoader(),
    DatetimeLoader(),
    TypeVarLoader(),
    UnionLoader(),
    DelayedAnnotationLoader(),
)

COMMON_CONVERTER_UNSTRICT = LoaderCollection(
    *_basic,
    DataclassLoader(True),
    EnumLoader(),
    DatetimeLoader(),
    TypeVarLoader(),
    UnionLoader(),
    DelayedAnnotationLoader(),
)

def from_json(cls: type[T], value: JsonType, \
                      loader: Loader[JsonType] | None = None,
                      allow_extra_keys: bool=False) -> T:
    '''Converts a value from JSON to a type T.

    If not specified, uses the default converter.'''
    if loader is None:
        if allow_extra_keys:
            loader = COMMON_CONVERTER_UNSTRICT
        else:
            loader = COMMON_CONVERTER
    context = DesCtx[JsonType](loader)
    context.parent_type = cls
    return context.des(value, cls)

async def from_json_async(cls: type[T], value: JsonType,
                            loader: Loader[JsonType]) -> T:
    '''Converts a value from JSON to a type T with support for async converters.'''

    return await recursive_await(DesCtx[JsonType](loader).des(value, cls))