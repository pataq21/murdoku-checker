from typing import ClassVar, Literal

from murdoku_checker.domain.grid_cell import Position
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.rules.positional_rule import (
    PositionalRule,
    next_to_positions,
)
from murdoku_checker.domain.rules.targets import FeatureElement, Target


class NextToRule(PositionalRule):
    """The person is orthogonally adjacent to the feature, in the same room."""

    DIFFICULTY: ClassVar[int] = 2

    type: Literal["next_to"] = "next_to"
    element: FeatureElement

    @property
    def clause(self) -> str:
        return f"{self.person} is next to a {self.element.value}"

    @property
    def difficulty(self) -> int:
        return self.DIFFICULTY

    @property
    def targets(self) -> tuple[Target, ...]:
        return (self.element,)

    def allowed_positions(self, map_: Map) -> frozenset[Position]:
        return next_to_positions(self.element.value, map_)
