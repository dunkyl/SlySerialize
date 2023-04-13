from collections.abc import Mapping as Map, Sequence as Seq
from typing import TypeAlias

JsonScalar: TypeAlias = int | float | bool | str | None
JsonType: TypeAlias = JsonScalar | list['JsonType'] | dict[str, 'JsonType']
JsonMap: TypeAlias = dict[str, JsonType]

JsonTypeCo: TypeAlias = JsonScalar | Seq['JsonTypeCo'] | Map[str, 'JsonTypeCo']
JsonMapCo: TypeAlias = Map[str, JsonTypeCo]