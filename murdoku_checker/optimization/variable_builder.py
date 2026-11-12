from dataclasses import dataclass
from types import MappingProxyType

from ortools.sat.python import cp_model

from murdoku_checker.domain import (
    AnyOf,
    In,
    Map,
    MurdokuInput,
    NextTo,
    NotNextTo,
    RelativePosition,
)
from murdoku_checker.domain.rule import Condition
from murdoku_checker.optimization.model import Variables
from murdoku_checker.optimization.positions import (
    Position,
    in_positions,
    next_to_positions,
    not_next_to_positions,
)


@dataclass(frozen=True, slots=True)
class VariableBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput) -> Variables:
        """Create one boolean variable per person and allowed cell.

        The variable is true when the person is located in that cell. Cells that
        a rule of the person already rules out, or that hold a non-occupiable
        feature (box, plant, table, tree, wardrobe), get no variable.
        """
        allowed_by_person = self._allowed_positions_by_person(input_)
        variables = {}
        for person in input_.people.people:
            allowed = allowed_by_person.get(person.name)
            for cell in input_.map.cells:
                if not cell.is_occupiable:
                    continue
                position = (cell.latitude, cell.longitude)
                if allowed is not None and position not in allowed:
                    continue
                variables[(person.name, *position)] = self.model.new_bool_var(
                    f"{person.name}@{cell.latitude},{cell.longitude}"
                )
        return MappingProxyType(variables)

    def _allowed_positions_by_person(
        self, input_: MurdokuInput
    ) -> dict[str, frozenset[Position]]:
        """Positions each restricted person can occupy; unrestricted people are absent."""
        allowed_by_person: dict[str, frozenset[Position]] = {}
        for rule in input_.rules.rules:
            allowed = self._allowed_positions(rule.condition, input_.map)
            if allowed is None:
                continue
            previous = allowed_by_person.get(rule.person)
            allowed_by_person[rule.person] = (
                allowed if previous is None else previous & allowed
            )
        return allowed_by_person

    def _allowed_positions(
        self, condition: Condition, map_: Map
    ) -> frozenset[Position] | None:
        """Positions satisfying the condition, or None if it does not restrict them."""
        if isinstance(condition, NextTo):
            return next_to_positions(condition, map_)
        if isinstance(condition, NotNextTo):
            return not_next_to_positions(condition, map_)
        if isinstance(condition, In):
            return in_positions(condition, map_)
        if isinstance(condition, RelativePosition):
            # The other person's position is not known until solving.
            return None
        if isinstance(condition, AnyOf):
            union: set[Position] = set()
            for child in condition.conditions:
                allowed = self._allowed_positions(child, map_)
                if allowed is None:
                    return None
                union |= allowed
            return frozenset(union)
        return None
