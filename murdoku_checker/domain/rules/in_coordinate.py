from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import Field

from murdoku_checker.domain.grid_cell import Coordinate, Position
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.rules.positional_rule import PositionalRule


class CoordinateAxis(StrEnum):
    ROW = "row"
    COLUMN = "column"


class InCoordinateRule(PositionalRule):
    """The person is in a given row (latitude) or column (longitude)."""

    DIFFICULTY: ClassVar[int] = 2

    type: Literal["in_coordinate"] = "in_coordinate"
    axis: CoordinateAxis = Field(strict=False)
    value: Coordinate

    @property
    def clause(self) -> str:
        # Coordinates are 0-based in the data but 1-based for the player.
        return f"{self.person} is in {self.axis.value} {self.value + 1}"

    @property
    def difficulty(self) -> int:
        return self.DIFFICULTY

    def allowed_positions(self, map_: Map) -> frozenset[Position]:
        index = 0 if self.axis is CoordinateAxis.ROW else 1
        return frozenset(
            position for position in map_.positions if position[index] == self.value
        )
