from itertools import combinations
from unittest.mock import patch

import pytest
from ortools.sat.python import cp_model

from murdoku_checker.apps.problem_builder import BuildProgress, build_problem
from murdoku_checker.apps.solution_checker import check_solutions, find_alternative
from murdoku_checker.domain import (
    AnyOfRule, CoordinateAxis, Direction, Element, Elements, FeatureElement,
    Gender, GridCell, InCoordinateRule, InRule,
    Map, MurdokuInput, People, Person, PersonElement, RelativePositionRule,
    RoomElement, Rules, Solution,
)


@pytest.fixture
def problem() -> tuple[MurdokuInput, Solution]:
    map_ = Map(cells=tuple(
        GridCell(latitude=row, longitude=column, room="room")
        for row in range(2) for column in range(2)
    ))
    rules = (
        InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=0),
        InCoordinateRule(person="Alice", axis=CoordinateAxis.COLUMN, value=0),
        InCoordinateRule(person="Bob", axis=CoordinateAxis.ROW, value=1),
        InCoordinateRule(person="Bob", axis=CoordinateAxis.COLUMN, value=1),
        InRule(person="Alice", element=RoomElement(value="room")),
    )
    return (
        MurdokuInput(
            map=map_,
            people=People(people=tuple(
                Person(name=name, gender=Gender.FEMALE, is_victim=name == "Bob")
                for name in ("Alice", "Bob")
            )),
            rules=Rules(rules=rules),
        ),
        Solution(map=map_, placements={"Alice": (0, 0), "Bob": (1, 1)}),
    )


@pytest.mark.parametrize("target_difficulty", [0, 4, 5, 6, 100])
def test_matches_exhaustive_lexicographic_optimum(
    problem: tuple[MurdokuInput, Solution], target_difficulty: int
) -> None:
    input_, target = problem
    pool = input_.rules.rules
    objectives = []
    for size in range(len(pool) + 1):
        for subset in combinations(pool, size):
            if not any("Alice" in rule.protagonists for rule in subset):
                continue
            puzzle = input_.model_copy(update={"rules": Rules(rules=subset)})
            if check_solutions(puzzle).count == 1:
                objectives.append((
                    abs(sum(rule.difficulty for rule in subset) - target_difficulty),
                    size,
                ))
    result = build_problem(
        input_, target, victim="Bob", target_difficulty=target_difficulty
    )
    assert (result.difficulty_error, len(result.puzzle.rules.rules)) == min(objectives)
    assert result.total_difficulty == sum(
        rule.difficulty for rule in result.puzzle.rules.rules
    )
    checked = check_solutions(result.puzzle)
    assert checked.count == 1
    assert checked.first_solution == target.placements


def test_difficulty_priority_outweighs_more_than_one_hundred_rules() -> None:
    features = tuple(f"feature_{index}" for index in range(102))
    map_ = Map(cells=(
        GridCell(latitude=0, longitude=0, room="room", features=features),
    ))
    simple = tuple(
        InRule(person="Alice", element=FeatureElement(value=name))
        for name in features
    )
    expensive = AnyOfRule(person="Alice", conditions=simple)
    input_ = MurdokuInput(
        map=map_,
        elements=Elements(elements=tuple(
            Element(name=name, is_occupiable=True) for name in features
        )),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(rules=(*simple, expensive)),
    )
    result = build_problem(
        input_, Solution(map=map_, placements={"Alice": (0, 0)}),
        victim="Alice", target_difficulty=102,
    )
    assert result.difficulty_error == 0
    assert result.puzzle.rules.rules == simple


def test_adds_cuts_until_the_target_is_unique(
    problem: tuple[MurdokuInput, Solution],
) -> None:
    input_, target = problem
    input_ = input_.model_copy(update={"rules": Rules(rules=input_.rules.rules[:2])})
    progress: list[BuildProgress] = []
    with patch(
        "murdoku_checker.apps.problem_builder.problem_builder.find_alternative",
        wraps=find_alternative,
    ) as checker:
        built = build_problem(
            input_, target, victim="Bob", target_difficulty=0,
            on_progress=progress.append,
        )
    assert built.iterations >= 2
    assert checker.call_count == built.iterations
    assert built.puzzle.rules == input_.rules
    assert [update.iteration for update in progress] == list(range(1, built.iterations + 1))
    assert [update.is_unique for update in progress] == (
        [False] * (built.iterations - 1) + [True]
    )
    for update, call in zip(progress, checker.call_args_list):
        rules = call.args[0].rules.rules
        assert update.total_difficulty == sum(rule.difficulty for rule in rules)
        assert update.target_difficulty == 0
        assert update.difficulty_error == abs(update.total_difficulty)
        assert update.rule_count == len(rules)
    assert progress[-1].difficulty_error == built.difficulty_error
    for call in checker.call_args_list[:-1]:
        candidate = call.args[0]
        assert check_solutions(candidate).count == 2


def test_coverage_requires_the_subject_and_excludes_victim(
    problem: tuple[MurdokuInput, Solution],
) -> None:
    input_, _ = problem
    map_ = Map(cells=(input_.map.cells[0], input_.map.cells[-1]))
    rule = RelativePositionRule(
        person="Bob", element=PersonElement(value="Alice"), direction=Direction.SOUTH
    )
    input_ = MurdokuInput(
        map=map_, people=input_.people, rules=Rules(rules=(rule,))
    )
    target = Solution(map=map_, placements={"Alice": (0, 0), "Bob": (1, 1)})
    with pytest.raises(ValueError, match="cannot cover"):
        build_problem(input_, target, victim="Bob", target_difficulty=0)

    alice_rule = RelativePositionRule(
        person="Alice", element=PersonElement(value="Bob"), direction=Direction.NORTH
    )
    input_ = input_.model_copy(update={"rules": Rules(rules=(rule, alice_rule))})
    result = build_problem(input_, target, victim="Bob", target_difficulty=0)
    assert result.puzzle.rules.rules == (alice_rule,)


@pytest.mark.parametrize("pool_size", [0, 1])
def test_insufficient_pool_fails_explicitly(
    problem: tuple[MurdokuInput, Solution], pool_size: int
) -> None:
    input_, target = problem
    input_ = input_.model_copy(update={
        "rules": Rules(rules=input_.rules.rules[:pool_size])
    })
    with pytest.raises(ValueError, match="cannot cover|cannot distinguish"):
        build_problem(input_, target, victim="Bob", target_difficulty=4)


def test_false_pool_rule_is_rejected(problem: tuple[MurdokuInput, Solution]) -> None:
    input_, target = problem
    false_rule = InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=1)
    input_ = input_.model_copy(update={"rules": Rules(rules=(false_rule,))})
    with pytest.raises(ValueError, match="Every pool rule"):
        build_problem(input_, target, victim="Bob", target_difficulty=4)


@pytest.mark.parametrize("status", [cp_model.UNKNOWN, cp_model.FEASIBLE, cp_model.MODEL_INVALID])
def test_unproven_master_optimum_is_an_error(
    problem: tuple[MurdokuInput, Solution], status: cp_model.CpSolverStatus
) -> None:
    input_, target = problem
    with patch.object(cp_model.CpSolver, "solve", return_value=status):
        with pytest.raises(RuntimeError, match="without a proven optimum"):
            build_problem(input_, target, victim="Bob", target_difficulty=4)


def test_alternative_excludes_the_whole_target(
    problem: tuple[MurdokuInput, Solution],
) -> None:
    input_, target = problem
    empty = input_.model_copy(update={"rules": Rules()})
    alternative = find_alternative(empty, target)
    assert alternative is not None
    assert alternative.placements != target.placements
    assert set(alternative.placements) == set(target.placements)
    assert find_alternative(input_, target) is None


def test_base_unique_target_can_use_an_empty_pool() -> None:
    map_ = Map(cells=(GridCell(latitude=0, longitude=0, room="room"),))
    input_ = MurdokuInput(
        map=map_, people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(),
    )
    result = build_problem(
        input_, Solution(map=map_, placements={"Alice": (0, 0)}),
        victim="Alice", target_difficulty=0,
    )
    assert result.puzzle.rules.rules == ()
    assert result.difficulty_error == 0


def test_invalid_target_cannot_be_reported_as_unique(
    problem: tuple[MurdokuInput, Solution],
) -> None:
    input_, target = problem
    for placements in (
        {"Alice": (0, 0)},
        {"Alice": (0, 0), "Bob": (0, 1)},
        {"Alice": (0, 0), "Bob": (1, 3)},
        {"Alice": (1, 1), "Bob": (0, 0)},
    ):
        with pytest.raises(ValueError):
            find_alternative(input_, Solution(map=target.map, placements=placements))


def test_inconclusive_subproblem_is_not_uniqueness(
    problem: tuple[MurdokuInput, Solution],
) -> None:
    input_, target = problem
    with patch.object(cp_model.CpSolver, "solve", return_value=cp_model.UNKNOWN):
        with pytest.raises(RuntimeError, match="without a conclusive result"):
            find_alternative(input_, target)
