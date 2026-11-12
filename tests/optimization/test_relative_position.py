import pytest
from ortools.sat.python import cp_model

from murdoku_checker.domain import (
    AnyOf,
    Cell,
    CellFeature,
    Direction,
    FeatureElement,
    Gender,
    In,
    Map,
    MurdokuInput,
    NextTo,
    NotNextTo,
    People,
    Person,
    PersonElement,
    RelativePosition,
    RoomElement,
    Rule,
    Rules,
)
from murdoku_checker.domain.rule import Condition
from murdoku_checker.optimization import ModelBuilder, OptimizationModel
from murdoku_checker.optimization.constraint_builder import ConstraintBuilder
from murdoku_checker.optimization.variable_builder import VariableBuilder


def relative(direction: Direction, target: str = "Bob") -> RelativePosition:
    return RelativePosition(direction=direction, element=PersonElement(value=target))


def make_input(*conditions: Condition, step: int = 2) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                Cell(
                    latitude=row * step,
                    longitude=column * step,
                    room="a" if row == 0 else "b",
                    features=(CellFeature.CARPET,) if row == column else (),
                )
                for row in range(2)
                for column in range(2)
            )
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(
            rules=tuple(
                Rule(person="Alice", condition=condition) for condition in conditions
            )
        ),
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
    condition = AnyOf(conditions=(relative(Direction.NORTH), relative(Direction.WEST)))

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 3


def test_nested_any_of_keeps_cells_allowed_by_relative_branch() -> None:
    condition = AnyOf(
        conditions=(
            In(element=RoomElement(value="a")),
            AnyOf(
                conditions=(
                    relative(Direction.SOUTH),
                    relative(Direction.NORTH, "Alice"),
                )
            ),
        )
    )

    model = ModelBuilder().build(make_input(condition))

    assert len(model.variables) == 8
    assert model.solve(max_solutions=None) == 4


def test_relative_position_any_of_does_not_force_false_branch() -> None:
    condition = AnyOf(
        conditions=(
            relative(Direction.NORTH, "Alice"),
            In(element=RoomElement(value="a")),
        )
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 2


def test_relative_position_intersects_with_static_filter() -> None:
    model = ModelBuilder().build(
        make_input(
            relative(Direction.NORTH),
            In(element=FeatureElement(value=CellFeature.CARPET)),
        )
    )

    result = model.solve_with_solution()

    assert result.count == 1
    assert result.first_solution == {"Alice": (0, 0), "Bob": (2, 2)}


@pytest.mark.parametrize(
    ("alternative", "expected"),
    [
        (In(element=FeatureElement(value=CellFeature.CARPET), is_unique=True), 7),
        (NextTo(element=FeatureElement(value=CellFeature.CARPET)), 10),
        (NotNextTo(element=FeatureElement(value=CellFeature.CARPET)), 10),
    ],
)
def test_relative_position_combines_with_other_rules(
    alternative: Condition, expected: int
) -> None:
    condition = AnyOf(conditions=(relative(Direction.NORTH), alternative))
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
        rules=Rules(rules=(Rule(person="Alice", condition=relative(Direction.SOUTH)),)),
    )

    assert ModelBuilder().build(input_).solve() == 0
