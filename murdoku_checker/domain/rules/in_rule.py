from typing import Annotated, Literal, TypeAlias

from ortools.sat.python import cp_model
from pydantic import Field, StrictBool

from murdoku_checker.domain.grid_cell import Position
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.literals import all_of_literal, any_of_literal
from murdoku_checker.domain.rules.positional_rule import PositionalRule
from murdoku_checker.domain.rules.targets import FeatureElement, RoomElement, Target
from murdoku_checker.domain.solution import Solution

InElement: TypeAlias = Annotated[
    RoomElement | FeatureElement,
    Field(discriminator="type"),
]


class InRule(PositionalRule):
    """The person is in a room or on a cell holding a feature.

    With is_unique, nobody else can be in that room or on that feature.
    """

    type: Literal["in"] = "in"
    element: InElement
    is_unique: StrictBool = False

    @property
    def clause(self) -> str:
        if isinstance(self.element, RoomElement):
            place = f"in the {self.element.value}"
        else:
            place = f"on a {self.element.value}"
        if self.is_unique:
            return f"{self.person} is the only person {place}"
        return f"{self.person} is {place}"

    @property
    def difficulty(self) -> int:
        return 2 if self.is_unique else 1

    @property
    def targets(self) -> tuple[Target, ...]:
        return (self.element,)

    def allowed_positions(self, map_: Map) -> frozenset[Position]:
        if isinstance(self.element, RoomElement):
            room = map_.get_room(self.element.value)
            return frozenset() if room is None else room.positions
        return map_.feature_positions(self.element.value)

    def evaluate(self, solution: Solution) -> bool:
        if not super().evaluate(solution):
            return False
        if not self.is_unique:
            return True
        allowed = self.allowed_positions(solution.map)
        return all(
            position not in allowed for _, position in solution.others(self.person)
        )

    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        person_in = super().to_literal(model, variables)
        if not self.is_unique:
            return person_in
        crowded = any_of_literal(model, self._others_inside(variables))
        return all_of_literal(model, [person_in, crowded.negated()])

    def apply_to_model(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> None:
        super().apply_to_model(model, variables)
        if self.is_unique:
            model.add_bool_and(
                [variable.negated() for variable in self._others_inside(variables)]
            )

    def _others_inside(self, variables: PlacementVariables) -> list[cp_model.IntVar]:
        allowed = self.allowed_positions(variables.map)
        return [
            variable
            for position, variable in variables.of_others(self.person)
            if position in allowed
        ]
