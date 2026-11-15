from collections import Counter

import pytest

from murdoku_checker.apps.pool_generator import generate_pool, iter_candidate_rules
from murdoku_checker.apps.solution_checker import ModelBuilder
from murdoku_checker.apps.solution_creator import generate_solution, generate_specification
from murdoku_checker.domain import (
    AnyOfRule,
    CoordinateAxis,
    Direction,
    FeatureElement,
    FeatureTargetRelation,
    Gender,
    GenerationConfig,
    GridCell,
    InCoordinateRule,
    InRule,
    Map,
    MurdokuInput,
    NextToRule,
    NotNextToRule,
    People,
    Person,
    PersonElement,
    RelativePositionRule,
    RoomElement,
    RoomRelationKind,
    RoomRelationRule,
    Rule,
    Rules,
    Solution,
)


@pytest.fixture(scope="module")
def solution() -> Solution:
    features = {(0, 0): ("chair",), (1, 1): ("chair",), (0, 1): ("lamp",)}
    return Solution(
        map=Map(
            cells=tuple(
                GridCell(
                    latitude=row,
                    longitude=column,
                    room="a" if column < 2 else "b",
                    features=features.get((row, column), ()),
                )
                for row in range(2)
                for column in range(3)
            )
        ),
        placements={"Alice": (0, 0), "Bob": (1, 2)},
    )


@pytest.fixture(scope="module")
def candidates(solution: Solution) -> list[Rule]:
    return list(iter_candidate_rules(solution))


@pytest.fixture(scope="module")
def pool(solution: Solution) -> list[Rule]:
    return generate_pool(solution)


def test_candidates_cover_all_simple_families_and_unique_same_person_pairs(
    candidates: list[Rule],
) -> None:
    simple = [rule for rule in candidates if not isinstance(rule, AnyOfRule)]
    assert Counter(rule.type for rule in simple) == {
        "in": 16,
        "next_to": 4,
        "not_next_to": 4,
        "in_coordinate": 10,
        "room_relation": 4,
        "relative_position": 100,
    }
    assert len(set(candidates)) == len(candidates)
    for person in ("Alice", "Bob"):
        person_simple = {rule for rule in simple if rule.person == person}
        pairs = [
            rule for rule in candidates
            if isinstance(rule, AnyOfRule) and rule.person == person
        ]
        assert len(pairs) == len(person_simple) * (len(person_simple) - 1) // 2
        for rule in pairs:
            assert len(rule.conditions) == 2
            assert rule.conditions[0] != rule.conditions[1]
            assert all(condition in person_simple for condition in rule.conditions)
            assert all(not isinstance(condition, AnyOfRule) for condition in rule.conditions)


def test_pool_contains_only_true_rules_and_rejects_every_false_candidate(
    solution: Solution, candidates: list[Rule], pool: list[Rule]
) -> None:
    assert pool
    assert all(rule.evaluate(solution) for rule in pool)
    accepted = set(pool)
    rejected = [rule for rule in candidates if not rule.evaluate(solution)]
    assert rejected
    assert not accepted.intersection(rejected)
    assert accepted.union(rejected) == set(candidates)


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (InRule(person="Alice", element=RoomElement(value="a")), True),
        (InRule(person="Alice", element=RoomElement(value="b")), False),
        (InRule(person="Alice", element=RoomElement(value="a"), is_unique=True), True),
        (InRule(person="Alice", element=FeatureElement(value="chair"), is_unique=True), True),
        (InRule(person="Bob", element=FeatureElement(value="chair")), False),
        (NextToRule(person="Alice", element=FeatureElement(value="lamp")), True),
        (NotNextToRule(person="Alice", element=FeatureElement(value="lamp")), False),
        (NotNextToRule(person="Bob", element=FeatureElement(value="lamp")), True),
        (InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=0), True),
        (InCoordinateRule(person="Alice", axis=CoordinateAxis.COLUMN, value=1), False),
        (RoomRelationRule(person="Alice", element=PersonElement(value="Bob"), relation=RoomRelationKind.SAME), False),
        (RoomRelationRule(person="Alice", element=PersonElement(value="Bob"), relation=RoomRelationKind.DIFFERENT), True),
        (RelativePositionRule(person="Alice", element=PersonElement(value="Bob"), direction=Direction.NORTH, offset=1), True),
        (RelativePositionRule(person="Alice", element=PersonElement(value="Bob"), direction=Direction.WEST, offset=2), True),
        (RelativePositionRule(person="Alice", element=PersonElement(value="Bob"), direction=Direction.WEST, offset=1), False),
        (RelativePositionRule(person="Bob", element=FeatureElement(value="chair"), direction=Direction.EAST, offset=2), True),
        (RelativePositionRule(person="Bob", element=FeatureElement(value="lamp"), direction=Direction.EAST, feature_relation=FeatureTargetRelation.NEXT_TO), True),
        (RelativePositionRule(person="Bob", element=FeatureElement(value="lamp"), direction=Direction.EAST, feature_relation=FeatureTargetRelation.IN), False),
    ],
    ids=lambda value: value.description if hasattr(value, "description") else str(value),
)
def test_expected_clues_are_accepted_or_rejected(
    rule: Rule, expected: bool, candidates: list[Rule], pool: list[Rule]
) -> None:
    assert rule in candidates
    assert (rule in pool) is expected


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (
            InRule(person="Alice", element=RoomElement(value="a")),
            InRule(person="Alice", element=RoomElement(value="b")),
            True,
        ),
        (
            InRule(person="Alice", element=RoomElement(value="a")),
            InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=0),
            True,
        ),
        (
            InRule(person="Alice", element=RoomElement(value="b")),
            InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=1),
            False,
        ),
    ],
    ids=["true-or-false", "true-or-true", "false-or-false"],
)
def test_disjunctions_use_candidates_before_filtering(
    first: Rule, second: Rule, expected: bool,
    candidates: list[Rule], pool: list[Rule],
) -> None:
    matching = [
        rule for rule in candidates
        if isinstance(rule, AnyOfRule)
        and frozenset(rule.conditions) == frozenset((first, second))
    ]
    assert len(matching) == 1
    assert (matching[0] in pool) is expected


def test_unique_clues_are_removed_when_another_person_shares_the_place() -> None:
    solution = Solution(
        map=Map(
            cells=(
                GridCell(latitude=0, longitude=0, room="a", features=("carpet",)),
                GridCell(latitude=1, longitude=1, room="a", features=("carpet",)),
            )
        ),
        placements={"Alice": (0, 0), "Bob": (1, 1)},
    )
    pool = generate_pool(solution)

    for element in (RoomElement(value="a"), FeatureElement(value="carpet")):
        assert InRule(person="Alice", element=element) in pool
        assert InRule(person="Alice", element=element, is_unique=True) not in pool


def test_sparse_coordinates_bound_offsets_by_real_map_distances() -> None:
    solution = Solution(
        map=Map(
            cells=tuple(
                GridCell(latitude=row, longitude=column, room="a")
                for row in (4, 8)
                for column in (10, 15)
            )
        ),
        placements={"Alice": (4, 10), "Bob": (8, 15)},
    )
    candidates = list(iter_candidate_rules(solution))
    assert {
        (rule.axis, rule.value)
        for rule in candidates if isinstance(rule, InCoordinateRule)
    } == {
        (CoordinateAxis.ROW, 4), (CoordinateAxis.ROW, 8),
        (CoordinateAxis.COLUMN, 10), (CoordinateAxis.COLUMN, 15),
    }
    for rule in candidates:
        if isinstance(rule, RelativePositionRule):
            distance = 4 if rule.direction in (Direction.NORTH, Direction.SOUTH) else 5
            assert rule.offset in (None, distance)
            assert rule.element.value != rule.person


def test_pool_order_does_not_depend_on_input_insertion_order(
    solution: Solution, pool: list[Rule]
) -> None:
    reordered = Solution(
        map=Map(cells=tuple(reversed(solution.map.cells))),
        placements=dict(reversed(tuple(solution.placements.items()))),
    )

    assert generate_pool(reordered) == pool


def test_no_people_produces_an_empty_pool() -> None:
    assert generate_pool(Solution(map=Map(), placements={})) == []


def test_person_outside_map_is_reported_instead_of_silently_filtered() -> None:
    with pytest.raises(ValueError, match="Alice is placed outside the map"):
        generate_pool(Solution(map=Map(), placements={"Alice": (0, 0)}))


def test_pool_integrates_with_generated_solution_serialization_and_solver() -> None:
    config = GenerationConfig(
        rows=2, columns=2, element_coverage_percent=0,
        element_type_count=0, room_count=1, seed=17,
    )
    generated = generate_solution(generate_specification(config))
    assert generated is not None

    pool = generate_pool(generated.solution)
    assert any(rule.person == generated.victim for rule in pool)
    rules = Rules(rules=tuple(pool))
    assert Rules.model_validate_json(rules.model_dump_json()) == rules
    assert all(rule.description and rule.difficulty > 0 for rule in pool)

    input_ = MurdokuInput(
        map=generated.solution.map,
        people=People(
            people=tuple(
                Person(name=name, gender=Gender.FEMALE, is_victim=name == generated.victim)
                for name in generated.solution.placements
            )
        ),
        rules=rules,
    )
    result = ModelBuilder().build(input_).solve_with_solution()
    assert result.count == 1
    assert result.first_solution == generated.solution.placements
