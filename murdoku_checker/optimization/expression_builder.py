from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput


@dataclass(frozen=True, slots=True)
class ExpressionBuilder:
    model: cp_model.CpModel

    def build(self, input_: MurdokuInput) -> None:
        return None
