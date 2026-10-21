from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput
from murdoku_checker.optimization.constraint_builder import ConstraintBuilder
from murdoku_checker.optimization.expression_builder import ExpressionBuilder
from murdoku_checker.optimization.model import OptimizationModel
from murdoku_checker.optimization.variable_builder import VariableBuilder


class ModelBuilder:
    def build(self, input_: MurdokuInput) -> OptimizationModel:
        model = cp_model.CpModel()

        variables = VariableBuilder(model).build(input_)
        ExpressionBuilder(model).build(input_)
        ConstraintBuilder(model).build(input_, variables)

        return OptimizationModel(input=input_, model=model, variables=variables)
