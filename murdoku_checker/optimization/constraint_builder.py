from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain import (
    AnyOf,
    Direction,
    In,
    Map,
    MurdokuInput,
    NotNextTo,
    RelativePosition,
)
from murdoku_checker.domain.rule import Condition
from murdoku_checker.optimization.model import Variables
from murdoku_checker.optimization.positions import (
    in_positions,
    next_to_positions,
    not_next_to_positions,
)


def _needs_rule_constraint(condition: Condition) -> bool:
    if isinstance(condition, AnyOf):
        return any(_needs_rule_constraint(child) for child in condition.conditions)
    return isinstance(condition, RelativePosition) or (
        isinstance(condition, In) and condition.is_unique
    )


@dataclass(frozen=True, slots=True)
class ConstraintBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput, variables: Variables) -> None:
        self.build_person_constraints(input_, variables)
        self.build_row_constraints(variables)
        self.build_column_constraints(variables)
        self.build_rule_constraints(input_, variables)

    def build_person_constraints(
        self, input_: MurdokuInput, variables: Variables
    ) -> None:
        """Each person is in exactly one cell.

        A person left without variables makes the model infeasible.
        """
        people: defaultdict[str, list[cp_model.IntVar]] = defaultdict(list)
        for (name, _, _), variable in variables.items():
            people[name].append(variable)
        for person in input_.people.people:
            self.model.add(sum(people[person.name]) == 1)

    def build_row_constraints(self, variables: Variables) -> None:
        """At most one person can be in each row (same latitude)."""
        rows: defaultdict[int, list[cp_model.IntVar]] = defaultdict(list)
        for (_, latitude, _), variable in variables.items():
            rows[latitude].append(variable)
        for row_variables in rows.values():
            self.model.add(sum(row_variables) <= 1)

    def build_column_constraints(self, variables: Variables) -> None:
        """At most one person can be in each column (same longitude)."""
        columns: defaultdict[int, list[cp_model.IntVar]] = defaultdict(list)
        for (_, _, longitude), variable in variables.items():
            columns[longitude].append(variable)
        for column_variables in columns.values():
            self.model.add(sum(column_variables) <= 1)

    def build_rule_constraints(
        self, input_: MurdokuInput, variables: Variables
    ) -> None:
        """Enforce rules depending on other people, including any_of branches."""
        for rule in input_.rules.rules:
            if _needs_rule_constraint(rule.condition):
                literal = self._condition_literal(
                    rule.person, rule.condition, input_.map, variables
                )
                self.model.add(literal == 1)

    def _condition_literal(
        self, person: str, condition: Condition, map_: Map, variables: Variables
    ) -> cp_model.IntVar:
        """Boolean variable that is true exactly when the condition holds."""
        if isinstance(condition, AnyOf):
            children = [
                self._condition_literal(person, child, map_, variables)
                for child in condition.conditions
            ]
            literal = self.model.new_bool_var("")
            self.model.add_bool_or(children).only_enforce_if(literal)
            self.model.add_bool_and(
                [child.negated() for child in children]
            ).only_enforce_if(literal.negated())
            return literal

        if isinstance(condition, RelativePosition):
            return self._relative_position_literal(person, condition, variables)

        if isinstance(condition, In):
            positions = in_positions(condition, map_)
        elif isinstance(condition, NotNextTo):
            positions = not_next_to_positions(condition, map_)
        else:
            positions = next_to_positions(condition, map_)
        person_in = self._any_of(
            [
                variable
                for (name, *position), variable in variables.items()
                if name == person and tuple(position) in positions
            ]
        )
        if not (isinstance(condition, In) and condition.is_unique):
            return person_in

        crowded = self._any_of(
            [
                variable
                for (name, *position), variable in variables.items()
                if name != person and tuple(position) in positions
            ]
        )
        literal = self.model.new_bool_var("")
        self.model.add_bool_and([person_in, crowded.negated()]).only_enforce_if(literal)
        self.model.add_bool_or([person_in.negated(), crowded]).only_enforce_if(
            literal.negated()
        )
        return literal

    def _relative_position_literal(
        self, person: str, condition: RelativePosition, variables: Variables
    ) -> cp_model.IntVar:
        vertical = condition.direction in (Direction.NORTH, Direction.SOUTH)
        coordinates = {
            name: cp_model.LinearExpr.sum(
                [
                    (latitude if vertical else longitude) * variable
                    for (candidate, latitude, longitude), variable in variables.items()
                    if candidate == name
                ]
            )
            for name in (person, condition.element.value)
        }
        # Exactly-one placement makes each weighted sum the person's coordinate.
        difference = coordinates[person] - coordinates[condition.element.value]
        literal = self.model.new_bool_var("")
        if condition.direction in (Direction.SOUTH, Direction.EAST):
            self.model.add(difference > 0).only_enforce_if(literal)
            self.model.add(difference <= 0).only_enforce_if(literal.negated())
        else:
            self.model.add(difference < 0).only_enforce_if(literal)
            self.model.add(difference >= 0).only_enforce_if(literal.negated())
        return literal

    def _any_of(self, operands: list[cp_model.IntVar]) -> cp_model.IntVar:
        """Boolean variable that is true when any operand is true."""
        literal = self.model.new_bool_var("")
        self.model.add_bool_or(operands).only_enforce_if(literal)
        self.model.add_bool_and([o.negated() for o in operands]).only_enforce_if(
            literal.negated()
        )
        return literal
