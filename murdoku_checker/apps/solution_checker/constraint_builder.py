from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput, PlacementVariables
from murdoku_checker.domain.placement_variables import Variables


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
        """Let every rule inject its own constraints."""
        placement = PlacementVariables(map=input_.map, variables=variables)
        for rule in input_.rules.rules:
            rule.apply_to_model(self.model, placement)
