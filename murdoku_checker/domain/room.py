from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from murdoku_checker.domain.grid_cell import GridCell, Position, RoomName


class Room(BaseModel):
    """A named area of the map made of the cells that share its name."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: RoomName
    cells: tuple[GridCell, ...] = Field(min_length=1, strict=False)

    @model_validator(mode="after")
    def validate_cells_belong_to_room(self) -> Self:
        for cell in self.cells:
            if cell.room != self.name:
                raise ValueError(
                    f"cell {cell.position} belongs to room {cell.room!r}, "
                    f"not {self.name!r}"
                )
        return self

    @property
    def positions(self) -> frozenset[Position]:
        return frozenset(cell.position for cell in self.cells)
