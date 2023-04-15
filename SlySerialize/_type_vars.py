from collections.abc import Mapping as Map, Sequence as Seq
from typing import TypeAlias, TypeVar

T = TypeVar('T')
U = TypeVar('U')
Self = TypeVar('Self')
Domain = TypeVar('Domain')

JsonScalar: TypeAlias = int | float | bool | str | None

JsonType: TypeAlias = JsonScalar | Seq['JsonType'] | Map[str, 'JsonType']
JsonMap: TypeAlias = Map[str, JsonType]