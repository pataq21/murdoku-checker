from abc import abstractmethod

from ortools.sat.python import cp_model

from murdoku_checker.domain.grid_cell import GridCell, Position
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.base_rule import BaseRule
from murdoku_checker.domain.rules.literals import any_of_literal
from murdoku_checker.domain.solution import Solution

_NEIGHBOUR_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def next_to_positions(feature: str, map_: Map) -> frozenset[Position]:
    """Cells at Manhattan distance 1 from the feature, in the same room."""
    positions: set[Position] = set()
    for cell in map_.cells:
        if feature not in cell.features:
            continue
        for d_latitude, d_longitude in _NEIGHBOUR_OFFSETS:
            latitude = cell.latitude + d_latitude
            longitude = cell.longitude + d_longitude
            if latitude < 0 or longitude < 0:
                continue
            neighbour: GridCell | None = map_.get_cell(latitude, longitude)
            if neighbour is not None and neighbour.room == cell.room:
                positions.add(neighbour.position)
    return frozenset(positions)


class PositionalRule(BaseRule):
    """Rule that only restricts the cells where its person can stand."""

    @abstractmethod
    def allowed_positions(self, map_: Map) -> frozenset[Position]:
        """Map positions where the person satisfies the rule."""

    def evaluate(self, solution: Solution) -> bool:
        return solution.position_of(self.person) in self.allowed_positions(
            solution.map
        )

    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        allowed = self.allowed_positions(variables.map)
        return any_of_literal(
            model,
            [
                variable
                for position, variable in variables.of(self.person).items()
                if position in allowed
            ],
        )

    def apply_to_model(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> None:
        allowed = self.allowed_positions(variables.map)
        model.add_bool_and(
            [
                variable.negated()
                for position, variable in variables.of(self.person).items()
                if position not in allowed
            ]
        )
