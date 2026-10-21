from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput


class _SolutionCounter(cp_model.CpSolverSolutionCallback):
    def __init__(self, max_solutions: int | None) -> None:
        super().__init__()
        self.count = 0
        self._max_solutions = max_solutions

    def on_solution_callback(self) -> None:
        self.count += 1
        if self._max_solutions is not None and self.count >= self._max_solutions:
            self.stop_search()


PersonCellKey = tuple[str, int, int]
Variables = Mapping[PersonCellKey, cp_model.IntVar]


@dataclass(frozen=True, slots=True)
class OptimizationModel:
    input: MurdokuInput
    model: cp_model.CpModel
    variables: Variables = field(default_factory=lambda: MappingProxyType({}))

    def solve(self, max_solutions: int | None = 2) -> int:
        """Count the solutions of the model, stopping at max_solutions.

        The default stops at 2, enough to tell no, a unique or several solutions
        apart. Use None to enumerate all of them.
        """
        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.log_search_progress = True
        counter = _SolutionCounter(max_solutions)

        status = solver.solve(self.model, counter)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE):
            raise RuntimeError(
                f"Solver ended without a conclusive result: {solver.status_name(status)}"
            )

        return counter.count
