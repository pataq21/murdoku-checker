from murdoku_checker.apps.solution_checker.model import SolveResult
from murdoku_checker.apps.solution_checker.model_builder import ModelBuilder
from murdoku_checker.domain import MurdokuInput, Solution


def check_solutions(
    input_: MurdokuInput, *, solver_logs: bool = False
) -> SolveResult:
    """Solve the puzzle looking for up to two solutions.

    A count of 1 proves the solution is unique; 2 means it is ambiguous.
    """
    return ModelBuilder().build(input_).solve_with_solution(
        max_solutions=2, solver_logs=solver_logs
    )


def find_alternative(
    input_: MurdokuInput, target: Solution, *, solver_logs: bool = False
) -> Solution | None:
    """Find a placement different from a valid target; None proves uniqueness."""
    names = {person.name for person in input_.people.people}
    if target.map != input_.map or set(target.placements) != names:
        raise ValueError("Target must use the input map and exactly its people")
    positions = tuple(target.placements.values())
    if (
        len({row for row, _ in positions}) != len(positions)
        or len({column for _, column in positions}) != len(positions)
    ):
        raise ValueError("Target repeats a row or column")
    for name in names:
        if not input_.is_cell_occupiable(target.cell_of(name)):
            raise ValueError(f"Target places {name} in a blocked cell")
    if any(not rule.evaluate(target) for rule in input_.rules.rules):
        raise ValueError("Every input rule must hold in the target")

    problem = ModelBuilder().build(input_)
    problem.model.add_bool_or(
        [
            problem.variables[name, row, column].Not()
            for name, (row, column) in target.placements.items()
        ]
    )
    result = problem.solve_with_solution(max_solutions=1, solver_logs=solver_logs)
    if result.first_solution is None:
        return None
    return Solution(map=input_.map, placements=result.first_solution)
