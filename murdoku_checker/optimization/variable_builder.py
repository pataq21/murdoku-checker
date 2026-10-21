from dataclasses import dataclass
from types import MappingProxyType

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput
from murdoku_checker.optimization.model import Variables


@dataclass(frozen=True, slots=True)
class VariableBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput) -> Variables:
        """Create one boolean variable per person and cell.

        The variable is true when the person is located in that cell.
        """
        variables = {
            (person.name, cell.latitude, cell.longitude): self.model.new_bool_var(
                f"{person.name}@{cell.latitude},{cell.longitude}"
            )
            for person in input_.people.people
            for cell in input_.map.cells
        }
        return MappingProxyType(variables)
