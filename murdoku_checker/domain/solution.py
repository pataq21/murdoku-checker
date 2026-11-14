from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from murdoku_checker.domain.grid_cell import GridCell, Position
from murdoku_checker.domain.map import Map


@dataclass(frozen=True, slots=True)
class Solution:
    """Placement of every person on a map."""

    map: Map
    placements: Mapping[str, Position]

    def __post_init__(self) -> None:
        object.__setattr__(self, "placements", MappingProxyType(dict(self.placements)))

    def position_of(self, person: str) -> Position:
        return self.placements[person]

    def cell_of(self, person: str) -> GridCell:
        cell = self.map.get_cell(*self.position_of(person))
        if cell is None:
            raise ValueError(f"{person} is placed outside the map")
        return cell

    def others(self, person: str) -> Iterator[tuple[str, Position]]:
        """Placements of everyone except the given person."""
        return (
            (name, position)
            for name, position in self.placements.items()
            if name != person
        )
