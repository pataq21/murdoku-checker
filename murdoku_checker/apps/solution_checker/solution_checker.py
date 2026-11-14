from murdoku_checker.apps.solution_checker.model import SolveResult
from murdoku_checker.apps.solution_checker.model_builder import ModelBuilder
from murdoku_checker.domain import MurdokuInput


def check_solutions(input_: MurdokuInput) -> SolveResult:
    """Solve the puzzle looking for up to two solutions.

    A count of 1 proves the solution is unique; 2 means it is ambiguous.
    """
    return ModelBuilder().build(input_).solve_with_solution(max_solutions=2)
