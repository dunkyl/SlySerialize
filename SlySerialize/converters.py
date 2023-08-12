'''Converter and Loader implementations for common types'''
import copy
import sys
from datetime import datetime, timezone
from enum import Enum
import inspect
from types import NoneType, UnionType
from typing import TypeVar, Any, get_origin, get_args
from dataclasses import is_dataclass, fields
from collections.abc import Mapping, Sequence
import typing
from asyncio import locks
import functools

from ._type_vars import *
from .abc import *

JsonDCtx = DesCtx[JsonType,]
JsonSCtx = SerCtx[JsonType]

def _origin(cls: T) -> T: return get_origin(cls) or cls

def _mismatch(actual: type, expected: Any):
    return TypeError(
        F"Mismatch: expected type {actual} to be represented as {expected}")

def _expect_type(value: Any, cls: type[T]|tuple[type[T], ...]) -> T:
    if not isinstance(value, cls):
        raise _mismatch(type(value), cls)
    return value

class JsonScalarConverter(Converter[JsonScalar, JsonType]):
    '''Converts common scalar types'''
    def can_load(self, cls: type) -> bool:
        return cls in (int, float, str, bool, NoneType)
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[JsonScalar]) -> JsonScalar:
        return _expect_type(value, cls)
    
    def ser(self, ctx: JsonSCtx, value: JsonScalar) -> JsonType: return value
    
class FromJsonLoader(Converter[JsonType, Any]):
    '''Converts classes that have a `from_json` method'''

    def can_load(self, cls: type) -> bool:
        return hasattr(cls, 'from_json')
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[Any]) -> Any:
        return getattr(cls, 'from_json')(value)
    
class ToJsonUnloader(Unloader[Any, JsonType]):
    '''Converts classes that have a `to_json` method'''

    def can_unload(self, cls: type) -> bool:
        return hasattr(cls, 'to_json')
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return getattr(value, 'to_json')()
    
class ToFromJsonConverter(ToJsonUnloader, FromJsonLoader, Converter[JsonType, JsonType]):
    '''Converts classes that have both `from_json` and `to_json` methods'''
    pass
    
class DataclassConverter(Converter[JsonType, Any]):
    '''Converts dataclasses'''
    allow_extra: bool

    def __init__(self, allow_extra_keys: bool) -> None:
        self.allow_extra = allow_extra_keys

    def can_load(self, cls: type) -> bool:
        return is_dataclass(_origin(cls))
    
    def can_unload(self, cls: type) -> bool: return self.can_load(cls)

    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[Any]) -> Any:
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
        dataclass = origin or cls
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
    
    def ser(self, ctx: JsonSCtx, value: Any) -> JsonType:
        return {
            f.name: ctx.ser(getattr(value, f.name))
            for f in fields(value)
        }
    
class DictConverter(Converter[dict[str, T], JsonType]):
    '''Converts dicts with string keys'''

    def can_load(self, cls: type):
        return _origin(cls) is dict and ((get_args(cls) or (str,))[0] is str)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[dict[str, T]]) -> dict[str, T]:
        if not isinstance(value, dict):
            raise _mismatch(type(value), dict)
        
        _, val_t = get_args(cls) or (str, JsonType)
        
        return dict({
            k: ctx.des(v, val_t)
            for k, v in value.items()
        }) # type: ignore - T is dict[str, vt]
    
    def ser(self, ctx: JsonSCtx, value: dict[str, T]) -> JsonType:
        return { k: ctx.ser(v) for k, v in value.items() }

class ListOrSetConverter(Converter[list[T] | set[T], JsonType]):
    '''Converts lists and sets'''
    
    def can_load(self, cls: type):
        return _origin(cls) in (list, set)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[list[T] | set[T]]) -> list[T] | set[T]:
        if not isinstance(value, list):
            raise _mismatch(type(value), list)
        
        concrete = _origin(cls)
        t, = get_args(cls) or (JsonType,)
        return concrete(
            ctx.des(v, t) for v in value
        )
    
    def ser(self, ctx: JsonSCtx, value: list[T] | set[T]) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class CollectionsAbcLoader(Loader[JsonType, Sequence[T] | Mapping[str, T]]):

    def can_load(self, cls: type):
        return _origin(cls) in (Sequence, Mapping)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type) -> Sequence[T] | Mapping[str, T]:
        concrete = _origin(cls)
        if concrete is Sequence:
            if not isinstance(value, list):
                raise _mismatch(type(value), list)
            
            t, = get_args(cls) or (JsonType,)
            return [
                ctx.des(v, t) for v in value
            ] # type: ignore - T is Seq[vt], list implements Seq
        else: # Mapping
            if not isinstance(value, dict):
                raise _mismatch(type(value), dict)
            _, val_t = get_args(cls) or (str, JsonType)
            return {
                k: ctx.des(v, val_t)
                for k, v in value.items()
            } # type: ignore - T is Map[str, vt], dict implements Map
    
class TupleConverter(Converter[tuple[Any, ...], JsonType]):
    '''Converts tuples'''
    def can_load(self, cls: type):
        return _origin(cls) is tuple
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[tuple[Any, ...]]) -> tuple[Any, ...]:
        if not isinstance(value, list):
            raise _mismatch(type(value), list)
        
        ts = get_args(cls) or tuple(JsonType for _ in value)

        if len(value) > len(ts):
            raise TypeError(F"Too few items in list {value} for {cls}") 
        
        return tuple(
            ctx.des(v, t) for v, t in zip(value, ts)
        ) # type: ignore - T is tuple[*ts]
    
    def ser(self, ctx: JsonSCtx, value: tuple[Any, ...]) -> JsonType:
        return [ ctx.ser(v) for v in value ]
    
class TypeVarLoader(Loader[Domain, T]):
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
    
class UnionLoader(Loader[Domain, T]):
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
    
class DatetimeConverter(Converter[datetime, JsonType]):
    '''Converts datetimes'''
    def can_load(self, cls: type):
        return cls is datetime
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[datetime]) -> datetime:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value).astimezone(timezone.utc)
        else:
            raise _mismatch(type(value), str|int|float)
        
    def ser(self, ctx: JsonSCtx, value: datetime) -> JsonType:
        return value.isoformat("T", 'milliseconds').replace('+00:00', 'Z')

EnumType = TypeVar("EnumType", bound=Enum)
class EnumConverter(Converter[EnumType, JsonType]):
    '''Converts string or integer enums'''
    def can_load(self, cls: type):
        return inspect.isclass(cls) and issubclass(cls, Enum)
    
    def can_unload(self, cls: type): return self.can_load(cls)
    
    def des(self, ctx: JsonDCtx, value: JsonType, cls: type[EnumType]) -> EnumType:
        if not isinstance(value, (str, int)):
            raise _mismatch(type(value), str|int)
        return cls(value)
    
    def ser(self, ctx: JsonSCtx, value: EnumType) -> JsonType:
        return value.value

class DelayedAnnotationLoader(Loader[Domain, T]):
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
    
class LoaderCollection(Loader[Domain, Any]):
    '''Collection of many loaders to handle many types at once'''
    loaders: list[Loader[Domain, Any]]

    def __init__(self, *loaders: Loader[Domain, Any]):
        self.loaders = list(loaders)

    def with_(self, *loaders: Loader[Domain, Any]):
        new = copy.deepcopy(self)
        new.loaders.extend(loaders)
        return new

    def can_load(self, cls: type) -> bool:
        return bool(self.find_loader(cls))
    
    @functools.lru_cache(maxsize=128)
    def find_loader(self, cls: type) -> Loader[Domain, Any] | None:
        for c in self.loaders:
            if c.can_load(cls):
                return c
        return None
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        des = self.find_loader(cls)
        # print(F"Selected converter: {des} for {type(value)}, {cls}")
        if des is None:
            raise TypeError(F"No loader for {cls}")
        return des.des(ctx, value, cls)


class UnloaderCollection(Unloader[Any, Domain]):
    '''Collection of many unloaders to handle many types at once'''
    unloaders: list[Unloader[Any, Domain]]

    def __init__(self, *unloaders: Unloader[Any, Domain]):
        self.unloaders = list(unloaders)

    def with_(self, *unloaders: Unloader[Any, Domain]):
        new = copy.deepcopy(self)
        new.unloaders.extend(unloaders)
        return new

    def can_unload(self, cls: type) -> bool:
        return bool(self.find_unloader(cls))
    
    @functools.lru_cache(maxsize=128)
    def find_unloader(self, cls: type) -> Unloader[Any, Domain] | None:
        for c in self.unloaders:
            if c.can_unload(cls):
                return c
        return None
    
    def ser(self, ctx: SerCtx[Domain], value: Any) -> Domain:
        ser = self.find_unloader(type(value))
        if ser is None:
            raise TypeError(F"No unloader for {type(value)}")
        return ser.ser(ctx, value)
    
class ConverterCollection(UnloaderCollection[Domain], LoaderCollection[Domain], Converter[Any, Domain]):
    '''Collection of many converters to handle many types at once'''

    def __init__(self, *converters: Converter[Any, Domain], loaders: list[Loader[Domain, Any]]|None = None, unloaders: list[Unloader[Any, Domain]]|None = None):
        self.unloaders = []
        self.loaders = []
        for c in converters:
            self.unloaders.append(c)
            self.loaders.append(c)
        for l in loaders or []:
            self.loaders.append(l)
        for u in unloaders or []:
            self.unloaders.append(u)

    def with_(self, *converters: Unloader[Any, Domain]|Loader[Domain, Any]):
        new = copy.deepcopy(self)
        for c in converters:
            if isinstance(c, Unloader):
                new.unloaders.append(c)
            if isinstance(c, Loader):
                new.loaders.append(c)
        return new
    
class PleaseWaitConverters(ConverterCollection[Domain]):
    '''Delays all conversions until complete() is called once.
    Useful when some converters depend on some variable, long 
    initialization process.'''
    wait_flag: locks.Event

    def __init__(self, *converters: Converter[Any, Domain]):
        super().__init__(*converters)
        self.wait_flag = locks.Event()

    def complete(self):
        self.wait_flag.set()

    async def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        await self.wait_flag.wait()
        return super().des(ctx, value, cls)