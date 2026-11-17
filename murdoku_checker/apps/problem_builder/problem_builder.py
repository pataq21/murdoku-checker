from collections.abc import Callable
from dataclasses import dataclass

from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_checker import find_alternative
from murdoku_checker.apps.solver_logging import configure_solver_logging
from murdoku_checker.domain import MurdokuInput, Rules, Solution


@dataclass(frozen=True, slots=True)
class BuiltProblem:
    puzzle: MurdokuInput
    total_difficulty: int
    difficulty_error: int
    iterations: int


@dataclass(frozen=True, slots=True)
class BuildProgress:
    iteration: int
    target_difficulty: int
    total_difficulty: int
    difficulty_error: int
    rule_count: int
    is_unique: bool


def build_problem(
    input_: MurdokuInput,
    target: Solution,
    *,
    victim: str,
    target_difficulty: int,
    solver_logs: bool = False,
    on_progress: Callable[[BuildProgress], None] | None = None,
) -> BuiltProblem:
    """Select an optimal unique puzzle from the pool in input_.rules.

    Coverage uses all protagonists except the victim. An insufficient pool
    raises ValueError; inconclusive solver results raise RuntimeError.
    When provided, on_progress receives one update per completed uniqueness check.
    """
    if type(target_difficulty) is not int or target_difficulty < 0:
        raise ValueError("target_difficulty must be a nonnegative integer")
    names = {person.name for person in input_.people.people}
    if victim not in names:
        raise ValueError(f"Unknown victim: {victim}")
    pool = input_.rules.rules
    if any(not rule.evaluate(target) for rule in pool):
        raise ValueError("Every pool rule must hold in the target")

    master = cp_model.CpModel()
    selected = [master.new_bool_var(f"x_{index}") for index in range(len(pool))]
    for name in sorted(names - {victim}):
        master.add_bool_or(
            [variable for rule, variable in zip(pool, selected)
             if name in rule.protagonists]
        )
    difficulties = [rule.difficulty for rule in pool]
    total = sum(difficulties)
    difficulty = sum(
        weight * variable for weight, variable in zip(difficulties, selected)
    )
    error = master.new_int_var(
        0, max(target_difficulty, abs(total - target_difficulty)), "difficulty_error"
    )
    master.add_abs_equality(error, difficulty - target_difficulty)
    # One unit of error must outweigh even selecting the entire pool.
    master.minimize(error * (len(pool) + 1) + sum(selected))
    solver = cp_model.CpSolver()
    configure_solver_logging(solver, solver_logs)
    solver.parameters.num_search_workers = 1
    iterations = 0

    while True:
        status = solver.solve(master)
        if status == cp_model.INFEASIBLE:
            raise ValueError("Clue pool cannot cover all non-victim people")
        if status != cp_model.OPTIMAL:
            raise RuntimeError(
                f"Master ended without a proven optimum: {solver.status_name(status)}"
            )
        iterations += 1
        chosen = tuple(
            rule for rule, variable in zip(pool, selected)
            if solver.boolean_value(variable)
        )
        puzzle = MurdokuInput(
            map=input_.map, elements=input_.elements, people=input_.people,
            rules=Rules(rules=chosen),
        )
        alternative = find_alternative(puzzle, target, solver_logs=solver_logs)
        total_difficulty = sum(rule.difficulty for rule in chosen)
        difficulty_error = solver.value(error)
        if on_progress is not None:
            on_progress(BuildProgress(
                iteration=iterations,
                target_difficulty=target_difficulty,
                total_difficulty=total_difficulty,
                difficulty_error=difficulty_error,
                rule_count=len(chosen),
                is_unique=alternative is None,
            ))
        if alternative is None:
            return BuiltProblem(
                puzzle=puzzle,
                total_difficulty=total_difficulty,
                difficulty_error=difficulty_error,
                iterations=iterations,
            )
        broken = [
            variable for rule, variable in zip(pool, selected)
            if not rule.evaluate(alternative)
        ]
        if not broken:
            raise ValueError("Clue pool cannot distinguish the target from an alternative")
        master.add_bool_or(broken)
