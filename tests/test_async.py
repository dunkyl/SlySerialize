import asyncio
from dataclasses import dataclass
from SlySerialize.converter import Converters, DesCtx
from SlySerialize.converters import DataclassConverter, JsonScalarConverter, ListOrSetConverter
from SlySerialize.de import convert_from_json

from SlySerialize.asynch import recursive_await, AsyncConverter

from SlySerialize.jsontype import JsonTypeCo

class RequiresAsync:
    value: int

    def __init__(self, value: int):
        self.value = value

    @classmethod
    async def from_json(cls, value: JsonTypeCo):
        if not isinstance(value, int):
            raise TypeError("Expected int")
        await asyncio.sleep(0.1)
        return RequiresAsync(value)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RequiresAsync):
            return False
        return self.value == other.value

@dataclass
class MemberRequiresAsync:
    async_member: RequiresAsync

    def to_json(self):
        return {'async_member': self.async_member.value}

async def test_async_from_json():
    x = MemberRequiresAsync(RequiresAsync(1))
    x_pending = convert_from_json(MemberRequiresAsync, x.to_json())
    print(x_pending)
    x_de = await recursive_await(x_pending)
    assert x == x_de

class MyAsync2:
    thing: str
    value: int
    next: 'MyAsync2 | None'

    def __init__(self, stuff: float, next: 'MyAsync2 | None'):
        self.value = int(stuff)
        self.thing = "hi"
        self.next = next

    def to_json(self) -> list[float]:
        if self.next is None:
            next_json = []
        else:
            next_json = self.next.to_json()
        return [self.value + 0.5] + next_json
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MyAsync2):
            return False
        return self.value == other.value and \
               self.thing == other.thing and \
                self.next == other.next

class MyClass2Converter(AsyncConverter[JsonTypeCo]):

    def can_convert(self, cls: type):
        return cls is MyAsync2
    
    async def des(self, ctx: DesCtx[JsonTypeCo], value: JsonTypeCo, cls: type[MyAsync2]) -> MyAsync2:
        if not isinstance(value, list):
            raise TypeError("Expected list")
        await asyncio.sleep(0.1)
        it = MyAsync2(value[-1], None) # type: ignore
        for v in reversed(value[:-1]):
            it = MyAsync2(v, it) # type: ignore
        return it

async def test_async_converter():

    json = [3.5, 2.5, 1.5]

    x = MyAsync2(3.5, MyAsync2(2.5, MyAsync2(1.5, None)))

    x_pending = convert_from_json(MyAsync2, json, converter=MyClass2Converter())

    x_de = await recursive_await(x_pending)

    assert x == x_de

async def test_async_converter_nested():

    @dataclass
    class MyData:
        async_member: MyAsync2
        other_member: list[int]
        more_async: list[MyAsync2]

    json = {
        'async_member': [3.5, 2.5, 1.5],
        'other_member': [1, 2, 3],
        'more_async': [[5.5, 5.5], [4.5, 4.5]]
    }

    x = MyData(
        MyAsync2(3.5, MyAsync2(2.5, MyAsync2(1.5, None))),
        [1, 2, 3],
        [MyAsync2(5.5, MyAsync2(5.5, None)), MyAsync2(4.5, MyAsync2(4.5, None))]
    )

    converter = Converters(
        JsonScalarConverter(),
        ListOrSetConverter(),
        DataclassConverter(False),
        MyClass2Converter()
    )

    x_pending = convert_from_json(MyData, json, converter=converter)

    x_de = await recursive_await(x_pending)

    assert x == x_de