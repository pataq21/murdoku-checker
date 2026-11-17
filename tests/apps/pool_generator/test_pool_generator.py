from collections import Counter
from unittest.mock import patch

import pytest

from murdoku_checker.apps.pool_generator import generate_pool, iter_candidate_rules
from murdoku_checker.apps.pool_generator import candidate_rules
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
from murdoku_checker.domain.generation_config import ALL_RULE_TYPES, RuleType


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
def pool(solution: Solution) -> dict[str, list[Rule]]:
    return generate_pool(solution)


def flatten_pool(pool: dict[str, list[Rule]]) -> list[Rule]:
    return [rule for rules in pool.values() for rule in rules]


@pytest.mark.parametrize("rule_type", ALL_RULE_TYPES)
def test_selecting_a_single_type_excludes_other_types(
    solution: Solution, candidates: list[Rule], pool: dict[str, list[Rule]],
    rule_type: RuleType,
) -> None:
    expected_candidates = [
        rule for rule in candidates
        if rule.type == rule_type and not isinstance(rule, AnyOfRule)
    ]
    assert list(iter_candidate_rules(solution, rule_types=(rule_type,))) == expected_candidates
    assert generate_pool(solution, rule_types=(rule_type,)) == {
        person: [
            rule for rule in rules
            if rule.type == rule_type and not isinstance(rule, AnyOfRule)
        ]
        for person, rules in pool.items()
    }


def test_disjunctions_only_use_enabled_simple_types(
    solution: Solution, candidates: list[Rule], pool: dict[str, list[Rule]],
) -> None:
    enabled: tuple[RuleType, ...] = ("in_coordinate", "any_of")

    def is_enabled(rule: Rule) -> bool:
        if isinstance(rule, AnyOfRule):
            return all(condition.type == "in_coordinate" for condition in rule.conditions)
        return rule.type == "in_coordinate"

    result = list(iter_candidate_rules(solution, rule_types=enabled))
    assert result == [rule for rule in candidates if is_enabled(rule)]
    assert any(isinstance(rule, AnyOfRule) for rule in result)
    assert generate_pool(solution, victim="Bob", rule_types=enabled) == {
        "Alice": [rule for rule in pool["Alice"] if is_enabled(rule)]
    }


def test_empty_rule_types_disable_all_clues(solution: Solution) -> None:
    assert list(iter_candidate_rules(solution, rule_types=())) == []
    assert generate_pool(solution, rule_types=()) == {"Alice": [], "Bob": []}


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
    solution: Solution, candidates: list[Rule], pool: dict[str, list[Rule]]
) -> None:
    pooled_rules = flatten_pool(pool)
    assert pool.keys() == solution.placements.keys()
    assert all(rule.person == person for person, rules in pool.items() for rule in rules)
    assert pooled_rules
    assert all(rule.evaluate(solution) for rule in pooled_rules)
    accepted = set(pooled_rules)
    rejected = [rule for rule in candidates if not rule.evaluate(solution)]
    both_true = [
        rule for rule in candidates
        if isinstance(rule, AnyOfRule)
        and all(condition.evaluate(solution) for condition in rule.conditions)
    ]
    assert rejected
    assert both_true
    assert not accepted.intersection(rejected)
    assert not accepted.intersection(both_true)
    assert accepted.union(rejected, both_true) == set(candidates)


def test_pool_disjunction_count_is_true_candidates_times_false_candidates(
    solution: Solution, candidates: list[Rule], pool: dict[str, list[Rule]]
) -> None:
    for person, rules in pool.items():
        simple = [
            rule for rule in candidates
            if rule.person == person and not isinstance(rule, AnyOfRule)
        ]
        true_count = sum(rule.evaluate(solution) for rule in simple)
        false_count = len(simple) - true_count
        disjunctions = [rule for rule in rules if isinstance(rule, AnyOfRule)]
        assert len(disjunctions) == true_count * false_count
        assert all(
            sum(condition.evaluate(solution) for condition in rule.conditions) == 1
            for rule in disjunctions
        )


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
    rule: Rule,
    expected: bool,
    candidates: list[Rule],
    pool: dict[str, list[Rule]],
) -> None:
    assert rule in candidates
    assert (rule in pool[rule.person]) is expected


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
            False,
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
    candidates: list[Rule], pool: dict[str, list[Rule]],
) -> None:
    matching = [
        rule for rule in candidates
        if isinstance(rule, AnyOfRule)
        and frozenset(rule.conditions) == frozenset((first, second))
    ]
    assert len(matching) == 1
    assert (matching[0] in pool[matching[0].person]) is expected


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
        assert InRule(person="Alice", element=element) in pool["Alice"]
        assert InRule(person="Alice", element=element, is_unique=True) not in pool["Alice"]


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
    solution: Solution, pool: dict[str, list[Rule]]
) -> None:
    reordered = Solution(
        map=Map(cells=tuple(reversed(solution.map.cells))),
        placements=dict(reversed(tuple(solution.placements.items()))),
    )

    assert generate_pool(reordered) == pool


def test_no_people_produces_an_empty_pool() -> None:
    assert generate_pool(Solution(map=Map(), placements={})) == {}


@pytest.mark.parametrize("victim", ["Alice", "Bob"])
def test_victim_candidates_are_not_built_but_other_pools_are_unchanged(
    solution: Solution, pool: dict[str, list[Rule]], victim: str
) -> None:
    with patch(
        "murdoku_checker.apps.pool_generator.candidate_rules._iter_simple_rules",
        wraps=candidate_rules._iter_simple_rules,
    ) as build_simple:
        result = generate_pool(solution, victim=victim)

    assert result == {person: rules for person, rules in pool.items() if person != victim}
    assert [call.args[1] for call in build_simple.call_args_list] == sorted(result)
    assert any(
        isinstance(target, PersonElement) and target.value == victim
        for rules in result.values() for rule in rules for target in rule.targets
    )


def test_unknown_victim_is_reported(solution: Solution) -> None:
    with pytest.raises(ValueError, match="Unknown victim: missing"):
        generate_pool(solution, victim="missing")


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

    pool = generate_pool(generated.solution, victim=generated.victim)
    assert generated.victim not in pool
    pooled_rules = flatten_pool(pool)
    rules = Rules(rules=tuple(pooled_rules))
    assert Rules.model_validate_json(rules.model_dump_json()) == rules
    assert all(rule.description and rule.difficulty > 0 for rule in pooled_rules)

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
