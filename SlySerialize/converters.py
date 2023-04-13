'''Loader implementations for common types'''
import copy
import sys
from datetime import datetime
from enum import Enum
import inspect
from types import NoneType, UnionType
from typing import TypeVar, Any, get_origin, get_args
from dataclasses import is_dataclass, fields
from collections.abc import Mapping, Sequence
import typing

from .typevars import T, U, Domain
from .jsontype import JsonType
from .converter import Converter, Unloader, DesCtx, SerCtx, Loader

JsonDCtx = DesCtx[JsonType]

def mismatch(actual: type, expected: Any):
    return TypeError(
        F"Mismatch: expected type {actual} to be represented as {expected}")

def expect_type(value: Any, cls: type[U]|tuple[type[U], ...]) -> U:
    if not isinstance(value, cls):
        raise mismatch(type(value), cls)
    return value

class JsonScalarConverter(Converter[JsonType]):
    '''Converts common scalar types'''
    def can_load(self, cls: type) -> bool:
        return cls in (int, float, str, bool, NoneType)
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        return expect_type(value, cls)
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType: return value
    
class FromJsonLoader(Converter[JsonType]):
    '''Converts classes that have a `from_json` method'''

    def can_load(self, cls: type) -> bool:
        return hasattr(cls, 'from_json')
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        return getattr(cls, 'from_json')(value)
    
class ToJsonUnloader(Unloader[JsonType]):
    '''Converts classes that have a `to_json` method'''

    def can_unload(self, cls: type) -> bool:
        return hasattr(cls, 'to_json')
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType:
        return getattr(value, 'to_json')()
    
class ToFromJsonConverter(ToJsonUnloader, FromJsonLoader, Converter[JsonType]):
    '''Converts classes that have both `from_json` and `to_json` methods'''
    pass
    
class DataclassConverter(Converter[JsonType]):
    '''Converts dataclasses'''
    allow_extra: bool

    def __init__(self, allow_extra_keys: bool) -> None:
        self.allow_extra = allow_extra_keys

    def can_load(self, cls: type) -> bool:
        return is_dataclass(get_origin(cls) or cls)
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, dict):
            raise mismatch(type(value), dict)
        dataclass = get_origin(cls) or cls
        inner_ctx = copy.copy(ctx)
        if origin := get_origin(cls):
            ts = get_args(cls)
            params: tuple[TypeVar, ...] = getattr(origin, '__parameters__')
            defined_type_params = {
                str(var): t # like ~T: int
                for var, t in zip(params, ts)
            }
            inner_ctx.type_vars = ctx.type_vars | defined_type_params
        inner_ctx.parent_type = dataclass

        fields_ = fields(dataclass)

        required = set(f.name for f in fields_)
        given = set(value.keys())

        if not self.allow_extra and (extra := given - required):
            raise TypeError(F"Unexpected fields {extra}")
        
        if missing := required - given:
            raise TypeError(F"Missing fields {missing}")
        
        return dataclass(**{
            f.name: inner_ctx.des(value[f.name], f.type)
            for f in fields(dataclass)
        })
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType:
        return {
            f.name: ctx.ser(getattr(value, f.name))
            for f in fields(value)
        }
    
class DictConverter(Converter[JsonType]):
    '''Converts dicts with string keys'''

    def can_load(self, cls: type):
        return (get_origin(cls) or cls) is dict and ((get_args(cls) or (str,))[0] is str)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, dict):
            raise mismatch(type(value), dict)
        
        _, val_t = get_args(cls) or (str, JsonType)
        
        return dict({
            k: ctx.des(v, val_t)
            for k, v in value.items()
        }) # type: ignore - T is dict[str, vt]
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType:
        return { k: ctx.ser(v) for k, v in value.items() }

class ListOrSetConverter(Converter[JsonType]):
    '''Converts lists and sets'''
    def can_load(self, cls: type):
        return (get_origin(cls) or cls) in (list, set)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, list):
            raise mismatch(type(value), list)
        
        concrete = get_origin(cls) or cls
        t, = get_args(cls) or (JsonType,)
        return concrete(
            ctx.des(v, t) for v in value
        )
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class CollectionsAbcLoader(Loader[JsonType]):

    def can_load(self, cls: type):
        return (get_origin(cls) or cls) in (Sequence, Mapping)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        concrete = get_origin(cls) or cls
        if concrete is Sequence:
            if not isinstance(value, list):
                raise mismatch(type(value), list)
            
            t, = get_args(cls) or (JsonType,)
            return [
                ctx.des(v, t) for v in value
            ] # type: ignore - T is Seq[vt], list implements Seq
        else: # Mapping
            if not isinstance(value, dict):
                raise mismatch(type(value), dict)
            _, val_t = get_args(cls) or (str, JsonType)
            return {
                k: ctx.des(v, val_t)
                for k, v in value.items()
            } # type: ignore - T is Map[str, vt], dict implements Map
    
class TupleConverter(Converter[JsonType]):
    '''Converts tuples'''
    def can_load(self, cls: type):
        return (get_origin(cls) or cls) is tuple
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, list):
            raise mismatch(type(value), list)
        
        ts = get_args(cls) or tuple(JsonType for _ in value)

        if len(value) > len(ts):
            raise TypeError(F"Too few items in list {value} for {cls}") 
        
        return tuple(
            ctx.des(v, t) for v, t in zip(value, ts)
        ) # type: ignore - T is tuple[*ts]
    
    def ser(self, ctx: SerCtx[JsonType], value: Any) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class TypeVarLoader(Loader[Domain]):
    '''Converts type variables inside of instances of generic types'''
    def can_load(self, cls: type):
        return type(cls) is TypeVar
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        name = str(cls)
        if name not in ctx.type_vars:
            raise ValueError(F"Unbound generic type variable {name} in {cls}")
        rec_ctx = copy.copy(ctx)
        rec_ctx.parent_type = cls
        return ctx.des(value, ctx.type_vars[name])
    
class UnionLoader(Loader[Domain]):
    '''Converts unions'''
    def can_load(self, cls: type):
        return type(cls) is UnionType or get_origin(cls) is typing.Union
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        possible_types = get_args(cls)
        if type(value) in possible_types:
            return value # type: ignore - value is already of the correct type
        attempt_errors: list[TypeError] = []
        for t in possible_types:
            try:
                return ctx.des(value, t)
            except TypeError as e:
                attempt_errors.append(e)
        raise TypeError(F"Failed to convert from {type(value)} to any of {possible_types}:\n" + "\n  ".join(str(e) for e in attempt_errors))
    
class DatetimeConverter(Converter[JsonType]):
    '''Converts datetimes'''
    def can_load(self, cls: type):
        return cls is datetime
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[datetime]) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        else:
            raise mismatch(type(value), str|int|float)
        
    def ser(self, ctx: SerCtx[JsonType], value: datetime) -> JsonType:
        return value.isoformat()

class EnumConverter(Converter[JsonType]):
    '''Converts string or integer enums'''
    def can_load(self, cls: type):
        return inspect.isclass(cls) and issubclass(cls, Enum)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, (str, int)):
            raise mismatch(type(value), str|int)
        return cls(value)
    
    def ser(self, ctx: SerCtx[JsonType], value: Enum) -> JsonType:
        return value.value

class DelayedAnnotationLoader(Loader[Domain]):
    '''Converts delayed annotations (string annotations)'''
    def can_load(self, cls: type):
        return type(cls) is str
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        print(F"Parent type: {ctx.parent_type}")
        if ctx.parent_type is not None:
            
            cls_globals = vars(sys.modules[ctx.parent_type.__module__]) \
                | { ctx.parent_type.__name__: ctx.parent_type }
        else:
            cls_globals = {}
        
        t = eval(cls, cls_globals) # type: ignore - cls is str
        return ctx.des(value, t)
    