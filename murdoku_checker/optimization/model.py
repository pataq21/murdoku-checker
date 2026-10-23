from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ortools.sat.python import cp_model

from murdoku_checker.domain import MurdokuInput


PersonCellKey = tuple[str, int, int]
Variables = Mapping[PersonCellKey, cp_model.IntVar]
Solution = Mapping[str, tuple[int, int]]


@dataclass(frozen=True, slots=True)
class SolveResult:
    """Count (possibly capped) and the first placement found, if any."""

    count: int
    first_solution: Solution | None


class _SolutionCounter(cp_model.CpSolverSolutionCallback):
    def __init__(self, variables: Variables, max_solutions: int | None) -> None:
        super().__init__()
        self.count = 0
        self.first_solution: Solution | None = None
        self._variables = variables
        self._max_solutions = max_solutions

    def on_solution_callback(self) -> None:
        if self.first_solution is None:
            self.first_solution = MappingProxyType(
                {
                    name: (latitude, longitude)
                    for (name, latitude, longitude), variable in self._variables.items()
                    if self.boolean_value(variable)
                }
            )
        self.count += 1
        if self._max_solutions is not None and self.count >= self._max_solutions:
            self.stop_search()


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
        return self.solve_with_solution(max_solutions).count

    def solve_with_solution(self, max_solutions: int | None = 2) -> SolveResult:
        """Count solutions up to the limit, retaining only the first placement.

        A count of 1 proves uniqueness only if the limit is at least 2 or None.
        An empty placement is a solution for an input without people; None
        means no solution was found.
        """
        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        counter = _SolutionCounter(self.variables, max_solutions)

        status = solver.solve(self.model, counter)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE):
            raise RuntimeError(
                f"Solver ended without a conclusive result: {solver.status_name(status)}"
            )

        return SolveResult(counter.count, counter.first_solution)
