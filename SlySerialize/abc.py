'Base classes for loaders, unloaders, and converters.'
from abc import ABC, abstractmethod
import asyncio

from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from typing_extensions import TypeForm

from collections.abc import Mapping as Map, Sequence as Seq

type JsonScalar = int | float | bool | str | None
type JsonType = JsonScalar | Seq[JsonType] | Map[str, JsonType]
type JsonMap = Map[str, JsonType]
    
type DesCtx[Domain] = LoadingContext[Domain]
type SerCtx[Domain] = UnloadingContext[Domain]

class LoadingContext[Domain]:
    'State for deserialization and recursion'

    type_vars: dict[str, type]
    parent_type: type[Any] | None
    parent_deserializer: Loader[Domain]
    only_sync: bool

    def __init__(self, converter: Loader[Domain], only_sync: bool):
        self.type_vars = {}
        self.parent_type = None
        self.only_sync = only_sync
        self.parent_deserializer = converter

    def des[T](self, value: Domain, cls: TypeForm[T]) -> T:
        result = self.parent_deserializer.des(self, value, cls)
        if self.only_sync:
            if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                raise ValueError("Async converter used in sync context")
        return result

class UnloadingContext[Domain]:
    'State for serialization and recursion'

    parent_serializer: Unloader[Domain]

    def __init__(self, converter: Unloader[Domain]):
        self.parent_serializer = converter

    def ser(self, value: Any) -> Domain:
        return self.parent_serializer.ser(self, value)
    

class Unloader[Domain](ABC):
    'Serializes one type or group of types'

    @abstractmethod
    def can_unload(self, cls: Any) -> bool:
        'Whether this converter should be used to serialize the given type'
        ...

    @abstractmethod
    def ser(self, ctx: SerCtx[Domain], value: Any) -> Domain:
        '''Convert a value to a domain-compatible type.
        
        Called only if `can_unload` returned `True` for `type(value)`.'''
        ...

class Loader[Domain](ABC):
    'Deserializes one type or group of types'

    @abstractmethod
    def can_load(self, cls: Any) -> bool:
        'Whether this converter should be used to deserialize the given type'
        ...

    @abstractmethod
    def des[T](self, ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T:
        '''Convert a domain value to the specified type.
        
        Called only if `can_load` returned `True` for `cls`.'''
        ...


class Converter[Domain](Unloader[Domain], Loader[Domain]):
    'Both serializes and deserializes one type or group of types T to and from Domain'
    pass


class AsyncLoader[Domain](Loader[Domain]):
    '''Deserializes one type or group of types asynchronously'''

    @abstractmethod
    async def des[T](self, # type: ignore - async override is by design
                  ctx: DesCtx[Domain], value: Domain, cls: TypeForm[T]) -> T: ... 
        
