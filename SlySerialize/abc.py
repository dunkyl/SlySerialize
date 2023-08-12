'Base classes for loaders, unloaders, and converters.'
from abc import ABC, abstractmethod
import asyncio

from typing import Any, Generic, TypeAlias

from ._type_vars import *

class LoadingContext(Generic[Domain, T]):
    'State for deserialization and recursion'

    type_vars: dict[str, type]
    parent_type: type | None
    parent_deserializer: 'Loader[Domain, T]'
    only_sync: bool

    def __init__(self, converter: 'Loader[Domain, T]', only_sync: bool):
        self.type_vars = {}
        self.parent_type = None
        self.only_sync = only_sync
        self.parent_deserializer = converter

    def des(self, value: Domain, cls: type[T]) -> T:
        result = self.parent_deserializer.des(self, value, cls)
        if self.only_sync:
            if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                raise ValueError("Async converter used in sync context")
        return result
    
DesCtx: TypeAlias = LoadingContext[Domain, Any]

class UnloadingContext(Generic[T, Domain]):
    'State for serialization and recursion'

    parent_serializer: 'Unloader[T, Domain]'

    def __init__(self, converter: 'Unloader[T, Domain]'):
        self.parent_serializer = converter

    def ser(self, value: T) -> Domain:
        return self.parent_serializer.ser(self, value)
    
SerCtx: TypeAlias = UnloadingContext[Any, Domain]

class Unloader(ABC, Generic[T, Domain]):
    'Serializes one type or group of types'

    @abstractmethod
    def can_unload(self, cls: type) -> bool:
        'Whether this converter should be used to serialize the given type'
        ...

    @abstractmethod
    def ser(self, ctx: SerCtx[Domain], value: T) -> Domain:
        '''Convert a value to a domain-compatible type.
        
        Called only if `can_unload` returned `True` for `type(value)`.'''
        ...

class Loader(ABC, Generic[Domain, T]):
    'Deserializes one type or group of types'

    @abstractmethod
    def can_load(self, cls: type) -> bool:
        'Whether this converter should be used to deserialize the given type'
        ...

    @abstractmethod
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        '''Convert a domain value to the specified type.
        
        Called only if `can_load` returned `True` for `cls`.'''
        ...


class Converter(Unloader[T, Domain], Loader[Domain, T]):
    'Both serializes and deserializes one type or group of types T to and from Domain'
    pass

class AsyncLoader(Loader[Domain, T]):
    '''Deserializes one type or group of types asynchronously'''

    @abstractmethod
    async def des(self, # type: ignore
                  ctx: DesCtx[Domain], value: Domain, cls: type) -> T: ... 
        
