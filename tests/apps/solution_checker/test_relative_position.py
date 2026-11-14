import pytest
from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_checker import ModelBuilder, OptimizationModel
from murdoku_checker.apps.solution_checker.constraint_builder import ConstraintBuilder
from murdoku_checker.apps.solution_checker.variable_builder import VariableBuilder
from murdoku_checker.domain import (
    AnyOfRule,
    BaseRule,
    Direction,
    Element,
    Elements,
    FeatureElement,
    Gender,
    GridCell,
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
    Rules,
)


def relative(direction: Direction, target: str = "Bob") -> RelativePositionRule:
    return RelativePositionRule(
        person="Alice", direction=direction, element=PersonElement(value=target)
    )


def any_of(*conditions: BaseRule) -> AnyOfRule:
    return AnyOfRule(person="Alice", conditions=conditions)


def make_input(*rules: BaseRule, step: int = 2) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                GridCell(
                    latitude=row * step,
                    longitude=column * step,
                    room="a" if row == 0 else "b",
                    features=("carpet",) if row == column else (),
                )
                for row in range(2)
                for column in range(2)
            )
        ),
        elements=Elements(
            elements=(Element(name="carpet", is_occupiable=True),)
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(rules=rules),
    )


def model_without_row_and_column_constraints(input_: MurdokuInput) -> OptimizationModel:
    model = cp_model.CpModel()
    variables = VariableBuilder(model).build(input_)
    builder = ConstraintBuilder(model)
    builder.build_person_constraints(input_, variables)
    builder.build_rule_constraints(input_, variables)
    return OptimizationModel(input_, model, variables)


@pytest.mark.parametrize("direction", list(Direction))
@pytest.mark.parametrize("full_constraints", [False, True])
def test_directions_compare_coordinates_strictly(
    direction: Direction, full_constraints: bool
) -> None:
    input_ = make_input(relative(direction))
    model = (
        ModelBuilder().build(input_)
        if full_constraints
        else model_without_row_and_column_constraints(input_)
    )

    result = model.solve_with_solution(max_solutions=None)

    assert result.count == (2 if full_constraints else 4)
    assert result.first_solution is not None
    alice = result.first_solution["Alice"]
    bob = result.first_solution["Bob"]
    assert {
        Direction.NORTH: alice[0] < bob[0],
        Direction.SOUTH: alice[0] > bob[0],
        Direction.WEST: alice[1] < bob[1],
        Direction.EAST: alice[1] > bob[1],
    }[direction]
    if full_constraints:
        assert alice[0] != bob[0]
        assert alice[1] != bob[1]


def test_multiple_direction_rules_intersect() -> None:
    model = ModelBuilder().build(
        make_input(relative(Direction.NORTH), relative(Direction.EAST))
    )

    result = model.solve_with_solution()

    assert result.count == 1
    assert result.first_solution == {"Alice": (0, 2), "Bob": (2, 0)}


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_offset_requires_exact_distance(
    direction: Direction,
) -> None:
    model = ModelBuilder().build(
        make_input(
            RelativePositionRule(
                person="Alice",
                direction=direction,
                element=PersonElement(value="Bob"),
                offset=2,
            )
        )
    )

    assert model.solve(max_solutions=None) == 2


def test_relative_position_offset_rejects_other_distances() -> None:
    model = ModelBuilder().build(
        make_input(
            RelativePositionRule(
                person="Alice",
                direction=Direction.SOUTH,
                element=PersonElement(value="Bob"),
                offset=1,
            )
        )
    )

    assert model.solve() == 0


@pytest.mark.parametrize(
    ("relation", "expected"),
    [
        (RoomRelationKind.SAME, 0),
        (RoomRelationKind.DIFFERENT, 4),
    ],
)
def test_room_relation_compares_people_rooms(
    relation: RoomRelationKind, expected: int
) -> None:
    condition = RoomRelationRule(
        person="Alice",
        relation=relation,
        element=PersonElement(value="Bob"),
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == expected


def test_room_relation_works_in_any_of() -> None:
    condition = any_of(
        RoomRelationRule(
            person="Alice",
            relation=RoomRelationKind.SAME,
            element=PersonElement(value="Bob"),
        ),
        relative(Direction.NORTH),
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 2


def test_opposing_directions_are_infeasible() -> None:
    model = ModelBuilder().build(
        make_input(relative(Direction.NORTH), relative(Direction.SOUTH))
    )

    assert model.solve() == 0


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_to_self_is_false(direction: Direction) -> None:
    model = ModelBuilder().build(make_input(relative(direction, "Alice")))

    assert model.solve() == 0


def test_any_of_unions_directions_without_counting_overlaps_twice() -> None:
    condition = any_of(relative(Direction.NORTH), relative(Direction.WEST))

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 3


def test_nested_any_of_keeps_cells_allowed_by_relative_branch() -> None:
    condition = any_of(
        InRule(person="Alice", element=RoomElement(value="a")),
        any_of(relative(Direction.SOUTH), relative(Direction.NORTH, "Alice")),
    )

    model = ModelBuilder().build(make_input(condition))

    assert len(model.variables) == 8
    assert model.solve(max_solutions=None) == 4


def test_relative_position_any_of_does_not_force_false_branch() -> None:
    condition = any_of(
        relative(Direction.NORTH, "Alice"),
        InRule(person="Alice", element=RoomElement(value="a")),
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 2


def test_relative_position_intersects_with_static_filter() -> None:
    model = ModelBuilder().build(
        make_input(
            relative(Direction.NORTH),
            InRule(person="Alice", element=FeatureElement(value="carpet")),
        )
    )

    result = model.solve_with_solution()

    assert result.count == 1
    assert result.first_solution == {"Alice": (0, 0), "Bob": (2, 2)}


@pytest.mark.parametrize(
    ("alternative", "expected"),
    [
        (
            InRule(
                person="Alice", element=FeatureElement(value="carpet"), is_unique=True
            ),
            7,
        ),
        (NextToRule(person="Alice", element=FeatureElement(value="carpet")), 10),
        (NotNextToRule(person="Alice", element=FeatureElement(value="carpet")), 10),
    ],
)
def test_relative_position_combines_with_other_rules(
    alternative: BaseRule, expected: int
) -> None:
    condition = any_of(relative(Direction.NORTH), alternative)
    model = model_without_row_and_column_constraints(make_input(condition, step=1))

    assert model.solve(max_solutions=None) == expected


def test_missing_placements_remain_infeasible() -> None:
    input_ = MurdokuInput(
        map=Map(),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(rules=(relative(Direction.SOUTH),)),
    )

    assert ModelBuilder().build(input_).solve() == 0
