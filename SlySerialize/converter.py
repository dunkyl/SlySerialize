from abc import ABC, abstractmethod
from asyncio import locks
import copy

from typing import Generic, TypeAlias

from .typevars import *


class DeserializtionContext(Generic[Domain]):
    '''State for deserialization and recursion'''
    type_vars: dict[str, type]
    parent_type: type | None
    parent_converter: 'Converter[Domain] | None'
    only_sync: bool

    def __init__(self, converter: 'Converter[Domain] | None' = None, only_sync: bool = False):
        self.type_vars = {}
        self.parent_type = None
        self.only_sync = only_sync
        self.parent_converter = converter

    def submit_converter(self, converter: 'Converter[Domain]'):
        if self.parent_converter is None:
            self.parent_converter = converter

    def des(self, value: Domain, cls: type[T]) -> T:
        if self.parent_converter is None:
            raise TypeError(F"Cannot deserialize {cls} without parent converter")
        result = self.parent_converter.des(self, value, cls)
        return result
    
DesCtx: TypeAlias = DeserializtionContext[Domain]

class Converter(ABC, Generic[Domain]):
    '''Deserializes one type or group of types'''
    @abstractmethod
    def can_convert(self: Self, cls: type) -> Self | None: pass

    @abstractmethod
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T: pass

    # def ser(self, value: object) -> JsonTypeCo: ...

class Converters(Converter[Domain]):
    '''Collection of many converters to handle many types at once'''
    converters: list[Converter[Domain]]

    def __init__(self, *converters: Converter[Domain]):
        self.converters = list(converters)

    def add(self, converter: Converter[Domain]):
        self.converters.append(converter)

    def with_(self, *converters: Converter[Domain]):
        new = copy.deepcopy(self)
        new.converters.extend(converters)
        return new

    def can_convert(self, cls: type) -> Converter[Domain] | None:
        for converter in self.converters:
            if converter.can_convert(cls):
                return converter
        return None
    
    def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T:
        converter = self.can_convert(cls)
        print(F"Selected converter: {converter} for {type(value)}, {cls}")
        if converter is None:
            raise TypeError(F"Cannot convert {cls} to Json")
        ctx.submit_converter(self)
        return converter.des(ctx, value, cls)
    
class PleaseWaitConverters(Converters[Domain]):
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