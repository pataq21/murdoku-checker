from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_checker.constraint_builder import ConstraintBuilder
from murdoku_checker.apps.solution_checker.model import OptimizationModel
from murdoku_checker.apps.solution_checker.variable_builder import VariableBuilder
from murdoku_checker.domain import MurdokuInput


class ModelBuilder:
    def build(self, input_: MurdokuInput) -> OptimizationModel:
        model = cp_model.CpModel()

        variables = VariableBuilder(model).build(input_)
        ConstraintBuilder(model).build(input_, variables)

        return OptimizationModel(input=input_, model=model, variables=variables)
