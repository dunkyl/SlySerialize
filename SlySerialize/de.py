'''
Extended support for deserialization of Python types from JSON
'''
from .converter import Converter, Converters, DesCtx
from .converters import *
from .asynch import recursive_await

_basic = (
    JsonScalarConverter(),
    ListOrSetConverter(),
    TupleConverter(),
    DictConverter(),
    FromJsonConverter(),
)

common_converter_strict = Converters(
    *_basic,
    DataclassConverter(False),
    EnumConverter(),
    DatetimeConverter(),
    TypeVarConverter(),
    UnionConverter(),
    DelayedAnnotationConverter(),
)

common_converter_unstrict = Converters(
    *_basic,
    DataclassConverter(True),
    EnumConverter(),
    DatetimeConverter(),
    TypeVarConverter(),
    UnionConverter(),
    DelayedAnnotationConverter(),
)

def convert_from_json(cls: type[T], value: JsonTypeCo, \
                      converter: Converter[JsonTypeCo] | None = None) -> T:
    '''Converts a value from JSON to a type T.

    If not specified, uses the default converter.'''
    if converter is None:
        converter = common_converter_strict
    return DesCtx[JsonTypeCo](converter).des(value, cls)

async def convert_from_json_async(cls: type[T], value: JsonTypeCo, \
                            converter: Converter[JsonTypeCo] | None = None) -> T:
    '''Converts a value from JSON to a type T with support for async converters.

    If not specified, uses the default converter.'''
    if converter is None:
        converter = common_converter_strict
    return await recursive_await(DesCtx[JsonTypeCo](converter).des(value, cls))