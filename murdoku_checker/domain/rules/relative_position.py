from enum import StrEnum
from typing import Annotated, Literal, Self, TypeAlias

from ortools.sat.python import cp_model
from pydantic import Field, model_validator

from murdoku_checker.domain.grid_cell import Position
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.base_rule import BaseRule
from murdoku_checker.domain.rules.literals import all_of_literal, any_of_literal
from murdoku_checker.domain.rules.positional_rule import next_to_positions
from murdoku_checker.domain.rules.targets import FeatureElement, PersonElement, Target
from murdoku_checker.domain.solution import Solution


class Direction(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class FeatureTargetRelation(StrEnum):
    IN = "in"
    NEXT_TO = "next_to"


RelativeElement: TypeAlias = Annotated[
    PersonElement | FeatureElement,
    Field(discriminator="type"),
]


class RelativePositionRule(BaseRule):
    """The person is north, south, east or west of someone.

    North and south compare latitudes, east and west longitudes. Without an
    offset any strictly positive distance works. A feature target stands for
    another, anonymous person who is on (or next to) that feature.
    """

    type: Literal["relative_position"] = "relative_position"
    direction: Direction = Field(strict=False)
    element: RelativeElement
    offset: Annotated[int, Field(ge=1)] | None = None
    feature_relation: FeatureTargetRelation = Field(
        default=FeatureTargetRelation.IN, strict=False
    )

    @model_validator(mode="after")
    def validate_feature_relation(self) -> Self:
        if (
            isinstance(self.element, PersonElement)
            and self.feature_relation is not FeatureTargetRelation.IN
        ):
            raise ValueError("feature_relation requires a feature element")
        return self

    @property
    def clause(self) -> str:
        if self.offset is None:
            distance = "somewhere"
        else:
            unit = "row" if self._is_vertical else "column"
            distance = f"exactly {self.offset} {unit}{'s' if self.offset > 1 else ''}"
        if isinstance(self.element, PersonElement):
            target = self.element.value
        elif self.feature_relation is FeatureTargetRelation.IN:
            target = f"a person on a {self.element.value}"
        else:
            target = f"a person next to a {self.element.value}"
        return f"{self.person} is {distance} {self.direction.value} of {target}"

    @property
    def difficulty(self) -> int:
        return (
            3
            + (self.offset is not None)
            + isinstance(self.element, FeatureElement)
        )

    @property
    def targets(self) -> tuple[Target, ...]:
        return (self.element,)

    def evaluate(self, solution: Solution) -> bool:
        own = self._coordinate(solution.position_of(self.person))
        if isinstance(self.element, PersonElement):
            other = solution.position_of(self.element.value)
            return self._matches(own - self._coordinate(other))
        feature_positions = self._feature_positions(solution.map)
        return any(
            position in feature_positions
            and self._matches(own - self._coordinate(position))
            for _, position in solution.others(self.person)
        )

    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        if isinstance(self.element, FeatureElement):
            return self._feature_literal(model, variables)

        coordinates = {
            name: cp_model.LinearExpr.sum(
                [
                    self._coordinate(position) * variable
                    for position, variable in variables.of(name).items()
                ]
            )
            for name in (self.person, self.element.value)
        }
        # Exactly-one placement makes each weighted sum the person's coordinate.
        difference = coordinates[self.person] - coordinates[self.element.value]
        literal = model.new_bool_var("")
        if self.offset is not None:
            expected = self._expected_difference(self.offset)
            model.add(difference == expected).only_enforce_if(literal)
            model.add(difference != expected).only_enforce_if(literal.negated())
        elif self._is_positive:
            model.add(difference > 0).only_enforce_if(literal)
            model.add(difference <= 0).only_enforce_if(literal.negated())
        else:
            model.add(difference < 0).only_enforce_if(literal)
            model.add(difference >= 0).only_enforce_if(literal.negated())
        return literal

    def _feature_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        feature_positions = self._feature_positions(variables.map)
        others = [
            (position, variable)
            for position, variable in variables.of_others(self.person)
            if position in feature_positions
        ]
        matches = [
            all_of_literal(model, [variable, other_variable])
            for position, variable in variables.of(self.person).items()
            for other_position, other_variable in others
            if self._matches(
                self._coordinate(position) - self._coordinate(other_position)
            )
        ]
        return any_of_literal(model, matches)

    def _feature_positions(self, map_: Map) -> frozenset[Position]:
        if self.feature_relation is FeatureTargetRelation.IN:
            return map_.feature_positions(self.element.value)
        return next_to_positions(self.element.value, map_)

    @property
    def _is_vertical(self) -> bool:
        return self.direction in (Direction.NORTH, Direction.SOUTH)

    @property
    def _is_positive(self) -> bool:
        return self.direction in (Direction.SOUTH, Direction.EAST)

    def _coordinate(self, position: Position) -> int:
        return position[0] if self._is_vertical else position[1]

    def _expected_difference(self, offset: int) -> int:
        return offset if self._is_positive else -offset

    def _matches(self, difference: int) -> bool:
        if self.offset is not None:
            return difference == self._expected_difference(self.offset)
        return difference > 0 if self._is_positive else difference < 0
