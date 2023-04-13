'''
Extended support for deserialization of Python types from JSON
'''
from .converter import Converter, Converters, DesCtx
from .converters import *

common_converter = Converters(
    JsonScalarConverter(),
    ListOrSetConverter(),
    TupleConverter(),
    DictConverter(),
    FromJsonConverter(),
    DataclassConverter(),
    EnumConverter(),
    DatetimeConverter(),
    TypeVarConverter(),
    UnionConverter(),
)

def convert_from_json(cls: type[T], value: JsonTypeCo, \
                      converter: Converter[JsonTypeCo] | None = None) -> T:
    '''Converts a value from JSON to a type T.

    If not specified, uses the default converter.'''
    if converter is None:
        converter = common_converter
    return converter.des(DesCtx[JsonTypeCo](), value, cls)