from collections import defaultdict
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    validate_call,
)

from murdoku_checker.domain.grid_cell import Coordinate, GridCell, Position
from murdoku_checker.domain.room import Room


class Map(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    cells: tuple[GridCell, ...] = Field(default=(), strict=False)
    _cells_by_position: Mapping[Position, GridCell] = PrivateAttr(
        default_factory=lambda: MappingProxyType({})
    )
    _rooms_by_name: Mapping[str, Room] = PrivateAttr(
        default_factory=lambda: MappingProxyType({})
    )

    @field_validator("cells")
    @classmethod
    def validate_unique_positions(
        cls, cells: tuple[GridCell, ...]
    ) -> tuple[GridCell, ...]:
        positions: set[Position] = set()
        for cell in cells:
            if cell.position in positions:
                raise ValueError(f"duplicate cell coordinates: {cell.position}")
            positions.add(cell.position)
        return cells

    def model_post_init(self, context: Any) -> None:
        self._cells_by_position = MappingProxyType(
            {cell.position: cell for cell in self.cells}
        )
        cells_by_room: defaultdict[str, list[GridCell]] = defaultdict(list)
        for cell in self.cells:
            cells_by_room[cell.room].append(cell)
        self._rooms_by_name = MappingProxyType(
            {
                name: Room(name=name, cells=tuple(cells_by_room[name]))
                for name in sorted(cells_by_room)
            }
        )

    @validate_call(config=ConfigDict(strict=True))
    def get_cell(
        self, latitude: Coordinate, longitude: Coordinate
    ) -> GridCell | None:
        return self._cells_by_position.get((latitude, longitude))

    @property
    def positions(self) -> frozenset[Position]:
        return frozenset(self._cells_by_position)

    @property
    def rooms(self) -> tuple[Room, ...]:
        """Rooms sorted by name."""
        return tuple(self._rooms_by_name.values())

    def get_room(self, name: str) -> Room | None:
        return self._rooms_by_name.get(name)

    def feature_positions(self, feature: str) -> frozenset[Position]:
        return frozenset(
            cell.position for cell in self.cells if feature in cell.features
        )
