from abc import abstractmethod
from typing import Any
import asyncio
from dataclasses import is_dataclass, fields

from .typevars import T, Domain
from .converter import DesCtx, Converter

class AsyncConverter(Converter[Domain]):
    '''Deserializes one type or group of types asynchronously'''

    @abstractmethod
    async def des(self, ctx: DesCtx[Domain], value: Domain, cls: type[T]) -> T: pass

async def recursive_await(value: asyncio.Future[Any] \
            | list[Any] | dict[str, Any] | set[Any] \
            | tuple[Any, ...] | Any
        ) -> Any:
    '''Await a value, or all values in it'''
    if asyncio.isfuture(value) or asyncio.iscoroutine(value):
        return await value
    if isinstance(value, list):
        return [await recursive_await(v) for v in value]
    elif isinstance(value, dict):
        return {k: await recursive_await(v) for k, v in value.items()}
    elif isinstance(value, set):
        return {await recursive_await(v) for v in value}
    elif isinstance(value, tuple):
        vals = [(await recursive_await(v)) for v in value]
        return tuple(*vals)
    elif is_dataclass(value):
        return type(value)(**{f.name: await recursive_await(getattr(value, f.name)) for f in fields(value)})
    else:
        print(F"Not awaiting {value}, {type(value)}")
        return value