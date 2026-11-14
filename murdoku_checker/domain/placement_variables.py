from collections.abc import Mapping
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain.grid_cell import Position
from murdoku_checker.domain.map import Map

PersonCellKey = tuple[str, int, int]
Variables = Mapping[PersonCellKey, cp_model.IntVar]


@dataclass(frozen=True, slots=True)
class PlacementVariables:
    """CP-SAT booleans telling whether a person stands on a cell of the map.

    Cells without a variable cannot hold that person.
    """

    map: Map
    variables: Variables

    def of(self, person: str) -> dict[Position, cp_model.IntVar]:
        return {
            (latitude, longitude): variable
            for (name, latitude, longitude), variable in self.variables.items()
            if name == person
        }

    def of_others(self, person: str) -> list[tuple[Position, cp_model.IntVar]]:
        return [
            ((latitude, longitude), variable)
            for (name, latitude, longitude), variable in self.variables.items()
            if name != person
        ]
