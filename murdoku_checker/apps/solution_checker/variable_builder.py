from dataclasses import dataclass
from types import MappingProxyType

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput
from murdoku_checker.domain.placement_variables import Variables


@dataclass(frozen=True, slots=True)
class VariableBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput) -> Variables:
        """Create one boolean variable per person and occupiable cell.

        The variable is true when the person is located in that cell. Cells
        holding an element marked as non-occupiable get no variable; rules
        restrict the remaining ones when applied to the model.
        """
        variables = {}
        for person in input_.people.people:
            for cell in input_.map.cells:
                if not input_.is_cell_occupiable(cell):
                    continue
                variables[(person.name, *cell.position)] = self.model.new_bool_var(
                    f"{person.name}@{cell.latitude},{cell.longitude}"
                )
        return MappingProxyType(variables)
