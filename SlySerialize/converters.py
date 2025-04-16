'''Converter and Loader implementations for common types'''
import copy
import sys
from datetime import datetime, timezone
from enum import Enum
import inspect
from types import NoneType, UnionType
from typing import TypeAliasType, TypeVar, Any, get_origin, get_args
from dataclasses import is_dataclass, fields
from collections.abc import Mapping, Sequence
import typing
from asyncio import locks
import functools

from .abc import *

JsonDCtx = DesCtx[JsonType]
JsonSCtx = SerCtx[JsonType]

def _origin[T](cls: T) -> T: return get_origin(cls) or cls

def _mismatch(actual: type, expected: Any):
    return TypeError(
        F"Mismatch: expected type {actual} to be represented as {expected}")

def _expect_type[T](value: object, cls: TypeForm[T]) -> T:
    if not isinstance(value, cls): # type: ignore
        raise _mismatch(type(value), cls)
    return value # type: ignore

class JsonScalarConverter(Converter[JsonType]):
    '''Converts common scalar types'''
    def can_load(self, cls: Any) -> bool:
        return cls in (int, float, str, bool, NoneType)
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        return _expect_type(value, cls)
    
    def ser(self, ctx: JsonSCtx, value: JsonScalar) -> JsonType: return value
    
class FromJsonLoader(Loader[JsonType]):
    '''Converts classes that have a `from_json` method'''

    def can_load(self, cls: type) -> bool:
        return hasattr(cls, 'from_json')
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        return getattr(cls, 'from_json')(value)
    
class ToJsonUnloader(Unloader[JsonType]):
    '''Converts classes that have a `to_json` method'''

    def can_unload(self, cls: Any) -> bool:
        return hasattr(cls, 'to_json')
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return getattr(value, 'to_json')()
    
class ToFromJsonConverter(ToJsonUnloader, FromJsonLoader, Converter[JsonType]):
    '''Converts classes that have both `from_json` and `to_json` methods'''
    pass
    
class DataclassConverter(Converter[JsonType]):
    '''Converts dataclasses'''
    allow_extra: bool

    def __init__(self, allow_extra_keys: bool) -> None:
        self.allow_extra = allow_extra_keys

    def can_load(self, cls: Any) -> bool:
        return is_dataclass(_origin(cls))
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if not isinstance(value, dict):
            raise _mismatch(type(value), dict)
        inner_ctx = copy.copy(ctx)
        if origin := get_origin(cls):
            ts = get_args(cls)
            params: tuple[TypeVar, ...] = getattr(origin, '__parameters__')
            defined_type_params = {
                str(var): t # like ~T: int
                for var, t in zip(params, ts)
            }
            inner_ctx.type_vars = ctx.type_vars | defined_type_params
        dataclass: Any = origin or cls # the dataclass constructor
        inner_ctx.parent_type = dataclass

        fields_ = fields(dataclass)

        required = set(f.name for f in fields_)
        given = set(value.keys())

        if not self.allow_extra and (extra := given - required):
            raise TypeError(F"Unexpected fields {extra}")
        
        if missing := required - given:
            raise TypeError(F"Missing fields {missing}")
        
        return dataclass(**{
            f.name: inner_ctx.des(value[f.name], f.type) # type: ignore - str supported as type
            for f in fields(dataclass)
        })
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return {
            f.name: ctx.ser(getattr(value, f.name))
            for f in fields(value)
        }
    
class DictStrConverter(Converter[JsonType]):
    '''Converts dicts with string keys'''

    def can_load(self, cls: Any):
        return _origin(cls) is dict and ((get_args(cls) or (str,))[0] is str)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if not isinstance(value, dict):
            raise _mismatch(type(value), dict)
        
        val_t: Any = get_args(cls)[1] or JsonType # map value type
        
        return dict({
            k: ctx.des(v, val_t) 
            for k, v in value.items()
        }) # type: ignore
    
    def ser(self, ctx: JsonSCtx, value: dict[str, Any]) -> JsonType:
        return { k: ctx.ser(v) for k, v in value.items() }

class ListOrSetConverter(Converter[JsonType]):
    '''Converts lists and sets'''
    
    def can_load(self, cls: Any):
        return _origin(cls) in (list, set)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if not isinstance(value, list):
            raise _mismatch(type(value), list)

        concrete: Any = _origin(cls) # exactly `list` or `set`
        t: Any = get_args(cls)[0] or JsonType # item type
        return concrete(
            ctx.des(v, t) for v in value 
        ) 
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class CollectionsAbcLoader(Loader[JsonType]):

    def can_load(self, cls: Any):
        return _origin(cls) in (Sequence, Mapping)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[Any]) -> Sequence[T] | Mapping[str, T]:
        concrete = _origin(cls)
        if concrete is Sequence:
            if not isinstance(value, list):
                raise _mismatch(type(value), list)
            
            t: Any = get_args(cls)[0] or JsonType # item type
            return [
                ctx.des(v, t) for v in value 
            ]
        else: # Mapping
            if not isinstance(value, dict):
                raise _mismatch(type(value), dict)
            val_t: Any = get_args(cls)[1] or JsonType # map value type
            return {
                k: ctx.des(v, val_t)
                for k, v in value.items()
            }
    
class TupleConverter(Converter[JsonType]):
    '''Converts tuples'''
    def can_load(self, cls: Any):
        return _origin(cls) is tuple
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if not isinstance(value, list):
            raise _mismatch(type(value), list)
        
        ts: Any = get_args(cls) or tuple(JsonType for _ in value) # each member type

        if len(value) > len(ts):
            raise TypeError(F"Too few items in list {value} for {cls}") 
        
        return tuple(
            ctx.des(v, t) for v, t in zip(value, ts)
        ) # type: ignore
    
    def ser(self, ctx: JsonSCtx, value: tuple[Any, ...]) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class TypeVarLoader[Domain](Loader[Domain]):
    '''Converts type variables inside of instances of generic types'''
    def can_load(self, cls: Any):
        return type(cls) is TypeVar
    
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        name = str(cls)
        if name not in ctx.type_vars:
            raise ValueError(F"Unbound generic type variable {name} in {cls}")
        rec_ctx = copy.copy(ctx)
        rec_ctx.parent_type = cls # type: ignore
        # TODO: test parent type as a typevar which is a non-class type
        # which contains a delayed annotation in it
        return ctx.des(value, ctx.type_vars[name]) # type: ignore - type var value is accepted
    
class UnionLoader[Domain](Loader[Domain]):
    '''Converts unions'''
    def can_load(self, cls: Any):
        return type(cls) is UnionType or get_origin(cls) is typing.Union
        # TODO: py 3.14
    
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
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
    def can_load(self, cls: Any):
        return cls is datetime
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00')) # type: ignore
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).astimezone(timezone.utc) # type: ignore
        else:
            raise _mismatch(type(value), str|int|float)
        
    def ser(self, ctx: JsonSCtx, value: datetime) -> JsonType:
        return value.isoformat("T", 'milliseconds').replace('+00:00', 'Z')

class EnumConverter(Converter[JsonType]):
    '''Converts string or integer enums'''
    def can_load(self, cls: Any):
        return inspect.isclass(cls) and issubclass(cls, Enum)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des[T](self, ctx: JsonDCtx, value: JsonType, cls: TypeForm[T]) -> T:
        if not isinstance(value, (str, int)):
            raise _mismatch(type(value), str|int)
        return cls(value) # type: ignore - cls is enum constructor
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return value.value

class TypeAliasLoader[Domain](Loader[Domain]):
    '''Loads TypeAliasType'''
    def can_load(self, cls: Any):
        return type(cls) is TypeAliasType
    
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        return ctx.des(value, cls.__value__) # type: ignore

class DelayedAnnotationLoader[Domain](Loader[Domain]):
    '''Converts delayed annotations (string annotations)'''
    def can_load(self, cls: Any):
        return type(cls) is str
    
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        print(F"Parent type: {ctx.parent_type}")
        if ctx.parent_type is not None:
            
            cls_globals = vars(sys.modules[ctx.parent_type.__module__]) \
                | { ctx.parent_type.__name__: ctx.parent_type }
        else:
            cls_globals = {}
        
        t = eval(cls, cls_globals) # type: ignore - cls is str
        return ctx.des(value, t)
    
class LoaderCollection[Domain](Loader[Domain]):
    '''Collection of many loaders to handle many types at once'''
    loaders: list[Loader[Domain]]

    def __init__(self, *loaders: Loader[Domain]):
        self.loaders = list(loaders)

    def with_(self, *loaders: Loader[Domain]):
        new = copy.deepcopy(self)
        new.loaders.extend(loaders)
        return new

    def can_load(self, cls: type) -> bool:
        return bool(self.find_loader(cls))
    
    @functools.lru_cache(maxsize=128)
    def find_loader(self, cls: type) -> Loader[Domain] | None:
        for c in self.loaders:
            if c.can_load(cls):
                return c
        return None
    
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        des = self.find_loader(cls)
        # print(F"Selected converter: {des} for {type(value)}, {cls}")
        if des is None:
            raise TypeError(F"No loader for {cls} ({type(cls)})")
        return des.des(ctx, value, cls)


class UnloaderCollection[Domain](Unloader[Domain]):
    '''Collection of many unloaders to handle many types at once'''
    unloaders: list[Unloader[Domain]]

    def __init__(self, *unloaders: Unloader[Domain]):
        self.unloaders = list(unloaders)

    def with_(self, *unloaders: Unloader[Domain]):
        new = copy.deepcopy(self)
        new.unloaders.extend(unloaders)
        return new

    def can_unload(self, cls: type) -> bool:
        return bool(self.find_unloader(cls))
    
    @functools.lru_cache(maxsize=128)
    def find_unloader(self, cls: type) -> Unloader[Domain] | None:
        for c in self.unloaders:
            if c.can_unload(cls):
                return c
        return None
    
    def ser(self, ctx: SerCtx[Domain], value: object) -> Domain:
        ser = self.find_unloader(type(value))
        if ser is None:
            raise TypeError(F"No unloader for {type(value)}")
        return ser.ser(ctx, value)
    
class ConverterCollection[Domain](UnloaderCollection[Domain], LoaderCollection[Domain], Converter[Domain]):
    '''Collection of many converters to handle many types at once'''

    def __init__(self, *converters: Converter[Domain], loaders: list[Loader[Domain]]|None = None, unloaders: list[Unloader[Domain]]|None = None):
        self.unloaders = []
        self.loaders = []
        for c in converters:
            self.unloaders.append(c)
            self.loaders.append(c)
        for l in loaders or []:
            self.loaders.append(l)
        for u in unloaders or []:
            self.unloaders.append(u)

    def with_(self, *converters: Unloader[Domain]|Loader[Domain]):
        new = copy.deepcopy(self)
        for c in converters:
            if isinstance(c, Unloader):
                new.unloaders.append(c)
            if isinstance(c, Loader):
                new.loaders.append(c)
        return new
    
class PleaseWaitConverters[Domain](ConverterCollection[Domain]):
    '''Delays all conversions until complete() is called once.
    Useful when some converters depend on some variable, long 
    initialization process.'''
    wait_flag: locks.Event

    def __init__(self, *converters: Converter[Domain]):
        super().__init__(*converters)
        self.wait_flag = locks.Event()

    def complete(self):
        self.wait_flag.set()

    async def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        await self.wait_flag.wait()
        return super().des(ctx, value, cls)