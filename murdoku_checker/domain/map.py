from types import MappingProxyType
from typing import Any, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    validate_call,
)

from murdoku_checker.domain.cell import Cell, Coordinate


class Map(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    cells: tuple[Cell, ...] = Field(default=(), strict=False)
    _cells_by_position: Mapping[tuple[int, int], Cell] = PrivateAttr(
        default_factory=lambda: MappingProxyType({})
    )

    @field_validator("cells")
    @classmethod
    def validate_unique_positions(cls, cells: tuple[Cell, ...]) -> tuple[Cell, ...]:
        positions: set[tuple[int, int]] = set()
        for cell in cells:
            position = (cell.latitude, cell.longitude)
            if position in positions:
                raise ValueError(f"duplicate cell coordinates: {position}")
            positions.add(position)
        return cells

    def model_post_init(self, context: Any) -> None:
        self._cells_by_position = MappingProxyType(
            {(cell.latitude, cell.longitude): cell for cell in self.cells}
        )

    @validate_call(config=ConfigDict(strict=True))
    def get_cell(self, latitude: Coordinate, longitude: Coordinate) -> Cell | None:
        return self._cells_by_position.get((latitude, longitude))