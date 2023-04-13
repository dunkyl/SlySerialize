'''Converter implementations for common types'''
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

from .typevars import T, Domain
from .jsontype import JsonType
from .converter import Converter, DesCtx

def mismatch(cls: type, expected: Any):
    return TypeError(
        F"Mismatch: expected type {cls} to be respresnted as {expected}")

class JsonScalarConverter(Converter[JsonType]):
    '''Converts common scalar types'''
    def can_convert(self, cls: type) -> bool:
        return cls in (int, float, str, bool, NoneType)

    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if isinstance(value, cls):
            return value
        raise mismatch(cls, type(value))
    
class FromJsonConverter(Converter[JsonType]):
    '''Converts classes that have a `from_json` method'''

    def can_convert(self, cls: type) -> bool:
        return hasattr(cls, 'from_json')
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        result = getattr(cls, 'from_json')(value)
        return result
    
class DataclassConverter(Converter[JsonType]):
    '''Converts dataclasses'''
    allow_extra_keys: bool

    def __init__(self, allow_extra_keys: bool) -> None:
        self.allow_extra_keys = allow_extra_keys

    def can_convert(self, cls: type) -> bool:
        return is_dataclass(get_origin(cls) or cls)

    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, dict):
            raise mismatch(type(value), dict)
        dataclass = get_origin(cls) or cls
        inner_ctx = copy.copy(ctx)
        if origin := get_origin(cls):
            targs = get_args(cls)
            params: tuple[TypeVar, ...] = getattr(origin, '__parameters__')
            defined_type_params = {
                str(var): t # like ~T: int
                for var, t in zip(params, targs)
            }
            inner_ctx.type_vars = ctx.type_vars | defined_type_params
        inner_ctx.parent_type = dataclass

        fields_ = fields(dataclass)

        if not self.allow_extra_keys:
            for key in value.keys():
                if key not in {f.name for f in fields_}:
                    raise TypeError(F"Unknown field {key} in {value}")
        
        return dataclass(**{
            f.name: inner_ctx.des(value[f.name], f.type)
            for f in fields(dataclass)
        })
    
class DictConverter(Converter[JsonType]):
    '''Converts dicts'''

    def can_convert(self, cls: type):
        return (get_origin(cls) or cls) is dict
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, dict):
            raise mismatch(type(value), dict)
        
        key_t, val_t = get_args(cls) or (str, JsonType)

        if key_t is not str:
            raise TypeError("dict with non-string keys is not supported")
        
        return dict({
            k: ctx.des(v, val_t)
            for k, v in value.items()
        }) # type: ignore - T is dict[str, vt]

class ListOrSetConverter(Converter[JsonType]):
    '''Converts lists and sets'''
    def can_convert(self, cls: type):
        return (get_origin(cls) or cls) in (list, set)
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, list):
            raise mismatch(type(value), list)
        
        concrete = get_origin(cls) or cls
        t, = get_args(cls) or (JsonType,)
        return concrete(
            ctx.des(v, t) for v in value
        )
    
class CollectionsAbcConverter(Converter[JsonType]):

    def can_convert(self, cls: type):
        return (get_origin(cls) or cls) in (Sequence, Mapping)
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
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
    def can_convert(self, cls: type):
        return (get_origin(cls) or cls) is tuple
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, list):
            raise mismatch(type(value), list)
        
        ts = get_args(cls) or tuple(JsonType for _ in value)

        if len(value) > len(ts):
            raise TypeError(F"Too few items in list {value} for {cls}") 
        
        return tuple(
            ctx.des(v, t) for v, t in zip(value, ts)
        ) # type: ignore - T is tuple[*ts]
    
class TypeVarConverter(Converter[Domain]):
    '''Converts type variables inside of instances of generic types'''
    def can_convert(self, cls: type):
        return type(cls) is TypeVar
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        name = str(cls)
        if name not in ctx.type_vars:
            raise ValueError(F"Unbound generic type variable {name} in {cls}")
        innerctx = copy.copy(ctx)
        innerctx.parent_type = cls
        return ctx.des(value, ctx.type_vars[name])
    
class UnionConverter(Converter[Domain]):
    '''Converts unions'''
    def can_convert(self, cls: type):
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
    def can_convert(self, cls: type):
        return cls is datetime
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[datetime]) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        else:
            raise mismatch(type(value), str|int|float)

class EnumConverter(Converter[JsonType]):
    '''Converts string or integer enums'''
    def can_convert(self, cls: type):
        return inspect.isclass(cls) and issubclass(cls, Enum)
    
    def des(self, ctx: DesCtx[JsonType], value: JsonType, cls: type[T]) -> T:
        if not isinstance(value, (str, int)):
            raise mismatch(type(value), str|int)
        return cls(value)

class DelayedAnnotationConverter(Converter[Domain]):
    '''Converts delayed annotations (string annotations)'''
    def can_convert(self, cls: type):
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
    