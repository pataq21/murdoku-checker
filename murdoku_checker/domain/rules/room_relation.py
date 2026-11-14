from enum import StrEnum
from typing import Literal

from ortools.sat.python import cp_model
from pydantic import Field

from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.base_rule import BaseRule
from murdoku_checker.domain.rules.targets import PersonElement, Target
from murdoku_checker.domain.solution import Solution


class RoomRelationKind(StrEnum):
    SAME = "same"
    DIFFERENT = "different"


class RoomRelationRule(BaseRule):
    """The person is in the same room as, or a different room from, someone."""

    type: Literal["room_relation"] = "room_relation"
    relation: RoomRelationKind = Field(strict=False)
    element: PersonElement

    @property
    def clause(self) -> str:
        if self.relation is RoomRelationKind.SAME:
            return f"{self.person} is in the same room as {self.element.value}"
        return f"{self.person} is in a different room from {self.element.value}"

    @property
    def difficulty(self) -> int:
        return 2 if self.relation is RoomRelationKind.SAME else 3

    @property
    def targets(self) -> tuple[Target, ...]:
        return (self.element,)

    def evaluate(self, solution: Solution) -> bool:
        same = (
            solution.cell_of(self.person).room
            == solution.cell_of(self.element.value).room
        )
        return same is (self.relation is RoomRelationKind.SAME)

    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        room_ids = {room.name: index for index, room in enumerate(variables.map.rooms)}
        room_by_position = {
            cell.position: room_ids[cell.room] for cell in variables.map.cells
        }
        rooms = {
            name: cp_model.LinearExpr.sum(
                [
                    room_by_position[position] * variable
                    for position, variable in variables.of(name).items()
                ]
            )
            for name in (self.person, self.element.value)
        }
        # Exactly-one placement makes each weighted sum the person's room id.
        difference = rooms[self.person] - rooms[self.element.value]
        literal = model.new_bool_var("")
        if self.relation is RoomRelationKind.SAME:
            model.add(difference == 0).only_enforce_if(literal)
            model.add(difference != 0).only_enforce_if(literal.negated())
        else:
            model.add(difference != 0).only_enforce_if(literal)
            model.add(difference == 0).only_enforce_if(literal.negated())
        return literal
