'''
Extended support for deserialization of Python types from JSON
'''
from .converter import Converter, Converters, DesCtx
from .converters import *

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
        converter = common_converter_unstrict
    return DesCtx[JsonTypeCo](converter).des(value, cls)

def convert_from_json_strict(cls: type[T], value: JsonTypeCo) -> T:
    '''Converts a value from JSON to a type T.

    Does not allow extra keys in dataclasses.

    If not specified, uses the default converter.'''
    return DesCtx[JsonTypeCo](common_converter_strict).des(value, cls)