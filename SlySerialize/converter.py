from abc import ABC, abstractmethod
from asyncio import locks
import copy
import functools

from typing import Any, Generic, TypeAlias

from .typevars import *


class LoadingContext(Generic[Domain]):
    '''State for deserialization and recursion'''
    type_vars: dict[str, type]
    parent_type: type | None
    parent_deserializer: 'Loader[Domain] | None'
    only_sync: bool

    def __init__(self, converter: 'Loader[Domain] | None' = None, only_sync: bool = False):
        self.type_vars = {}
        self.parent_type = None
        self.only_sync = only_sync
        self.parent_deserializer = converter

    def submit_converter(self, converter: 'Loader[Domain]'):
        if self.parent_deserializer is None:
            self.parent_deserializer = converter

    def des(self, value: Domain, cls: type[T]) -> T:
        if self.parent_deserializer is None:
            raise TypeError(F"Cannot deserialize {cls} without parent converter")
        result = self.parent_deserializer.des(self, value, cls)
        return result
    
DesCtx: TypeAlias = LoadingContext[Domain]


class Unloader(ABC, Generic[Domain]):
    '''Serializes one type or group of types'''

    @abstractmethod
    def can_unload(self, cls: type) -> bool: pass

    @abstractmethod
    def ser(self, value: Any) -> Domain: ...

class Loader(ABC, Generic[Domain]):
    '''Deserializes one type or group of types'''

    @abstractmethod
    def can_load(self, cls: type) -> bool: pass

    @abstractmethod
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T: ...


class Converter(Unloader[Domain], Loader[Domain]):
    '''Both serializes and deserializes one type or group of types'''
    pass
    

class LoaderCollection(Loader[Domain]):
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
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        des = self.find_loader(cls)
        print(F"Selected converter: {des} for {type(value)}, {cls}")
        if des is None:
            raise TypeError(F"No loader for {cls}")
        ctx.submit_converter(self)
        return des.des(ctx, value, cls)
    
class UnloaderCollection(Unloader[Domain]):
    '''Collection of many unloaders to handle many types at once'''
    unloaders: list[Unloader[Domain]]

    def __init__(self, *unloaders: Unloader[Domain]):
        self.unloaders = list(unloaders)

    def with_(self, *unloaders: Unloader[Domain]):
        new = copy.deepcopy(self)
        new.unloaders.extend(unloaders)
        return new

    def can_load(self, cls: type) -> bool:
        return bool(self.find_unloader(cls))
    
    @functools.lru_cache(maxsize=128)
    def find_unloader(self, cls: type) -> Unloader[Domain] | None:
        for c in self.unloaders:
            if c.can_unload(cls):
                return c
        return None
    
    def ser(self, value: object) -> Domain:
        ser = self.find_unloader(type(value))
        if ser is None:
            raise TypeError(F"No unloader for {type(value)}")
        return ser.ser(value)
    
class PleaseWaitConverters(LoaderCollection[Domain]):
    '''Delays all conversions until complete() is called once.
    Useful when some converters depend on some variable, long 
    initialization process.'''
    wait_flag: locks.Event

    def __init__(self, *converters: Converter[Domain]):
        super().__init__(*converters)
        self.wait_flag = locks.Event()

    def complete(self):
        self.wait_flag.set()

    async def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        await self.wait_flag.wait()
        return super().des(ctx, value, cls)