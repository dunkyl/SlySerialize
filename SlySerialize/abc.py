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
    
type DesCtx[Stored] = LoadingContext[Stored, Any]
type SerCtx[Stored] = UnloadingContext[Stored, Any]

class LoadingContext[Stored, Target]:
    'State for deserialization and recursion'

    type_vars: dict[str, type]
    parent_type: type[Any] | None
    parent_deserializer: Loader[Stored, Target]
    only_sync: bool

    def __init__(self, converter: Loader[Stored, Target], only_sync: bool):
        self.type_vars = {}
        self.parent_type = None
        self.only_sync = only_sync
        self.parent_deserializer = converter

    def des(self, value: Stored, cls: TypeForm[Target]) -> Target:
        result = self.parent_deserializer.des(self, value, cls)
        if self.only_sync:
            if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                raise ValueError("Async converter used in sync context")
        return result

class UnloadingContext[Stored, Target]:
    'State for serialization and recursion'

    parent_serializer: Unloader[Stored, Target]

    def __init__(self, converter: Unloader[Stored, Target]):
        self.parent_serializer = converter

    def ser(self, value: Target) -> Stored:
        return self.parent_serializer.ser(self, value)
    

class Unloader[Stored, Target](ABC):
    'Serializes one type or group of types'

    @abstractmethod
    def can_unload(self, cls: Any) -> bool:
        'Whether this converter should be used to serialize the given type'
        ...

    @abstractmethod
    def ser(self, ctx: UnloadingContext[Stored, Target], value: Target) -> Stored:
        '''Convert a value to a domain-compatible type.
        
        Called only if `can_unload` returned `True` for `type(value)`.'''
        ...

class Loader[Stored, Target](ABC):
    'Deserializes one type or group of types'

    @abstractmethod
    def can_load(self, cls: Any) -> bool:
        'Whether this converter should be used to deserialize the given type'
        ...

    @abstractmethod
    def des(self, ctx: LoadingContext[Stored, Target], value: Stored, cls: TypeForm[Target]) -> Target:
        '''Convert a domain value to the specified type.
        
        Called only if `can_load` returned `True` for `cls`.'''
        ...


class Converter[Stored, Target](Unloader[Stored, Target], Loader[Stored, Target]):
    'Both serializes and deserializes one type or group of types T to and from Stored'
    pass


class AsyncLoader[Stored, Target](Loader[Stored, Target]):
    '''Deserializes one type or group of types asynchronously'''

    @abstractmethod
    async def des(self, # type: ignore - async override is by design
                  ctx: DesCtx[Stored], value: Stored, cls: TypeForm[Target]) -> Target: ... 
        
