'''
Extended support for deserialization of Python types from JSON
'''
from .converter import Converter, Converters, DesCtx
from .converters import *
from .asynch import recursive_await

_basic = (
    JsonScalarConverter(),
    ListOrSetConverter(),
    CollectionsAbcConverter(),
    TupleConverter(),
    DictConverter(),
    FromJsonConverter(),
)

COMMON_CONVERTER = Converters(
    *_basic,
    DataclassConverter(False),
    EnumConverter(),
    DatetimeConverter(),
    TypeVarConverter(),
    UnionConverter(),
    DelayedAnnotationConverter(),
)

COMMON_CONVERTER_UNSTRICT = Converters(
    *_basic,
    DataclassConverter(True),
    EnumConverter(),
    DatetimeConverter(),
    TypeVarConverter(),
    UnionConverter(),
    DelayedAnnotationConverter(),
)

def convert_from_json(cls: type[T], value: JsonType, \
                      converter: Converter[JsonType] | None = None) -> T:
    '''Converts a value from JSON to a type T.

    If not specified, uses the default converter.'''
    if converter is None:
        converter = COMMON_CONVERTER
    return DesCtx[JsonType](converter).des(value, cls)

def convert_from_json_unstrict(cls: type[T], value: JsonType, ) -> T:
    '''Converts a value from JSON to a type T.

    Uses the default converter and allows unused fields for dataclasses.'''
    return convert_from_json(cls, value, COMMON_CONVERTER_UNSTRICT)

async def convert_from_json_async(cls: type[T], value: JsonType, \
                            converter: Converter[JsonType] | None = None) -> T:
    '''Converts a value from JSON to a type T with support for async converters.

    If not specified, uses the default converter.'''
    if converter is None:
        converter = COMMON_CONVERTER
    return await recursive_await(DesCtx[JsonType](converter).des(value, cls))