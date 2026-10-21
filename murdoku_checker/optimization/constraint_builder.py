from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput
from murdoku_checker.optimization.model import Variables


@dataclass(frozen=True, slots=True)
class ConstraintBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput, variables: Variables) -> None:
        self.build_person_constraints(variables)
        self.build_row_constraints(variables)
        self.build_column_constraints(variables)

    def build_person_constraints(self, variables: Variables) -> None:
        """Each person is in exactly one cell."""
        people: defaultdict[str, list[cp_model.IntVar]] = defaultdict(list)
        for (name, _, _), variable in variables.items():
            people[name].append(variable)
        for person_variables in people.values():
            self.model.add(sum(person_variables) == 1)

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
