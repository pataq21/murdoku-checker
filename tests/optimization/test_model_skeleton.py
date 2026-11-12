from unittest.mock import call, patch

import pytest
from ortools.sat.python import cp_model

from murdoku_checker.domain import (
    AnyOf,
    Cell,
    CellFeature,
    FeatureElement,
    In,
    Map,
    MurdokuInput,
    NextTo,
    NotNextTo,
    People,
    RoomElement,
    Rule,
    Rules,
)
from murdoku_checker.domain.person import Gender, Person
from murdoku_checker.optimization import ModelBuilder, OptimizationModel
from murdoku_checker.optimization.constraint_builder import ConstraintBuilder
from murdoku_checker.optimization.expression_builder import ExpressionBuilder
from murdoku_checker.optimization.model import _SolutionCounter
from murdoku_checker.optimization.variable_builder import VariableBuilder


def make_input() -> MurdokuInput:
    return MurdokuInput(map=Map(), people=People(), rules=Rules())


@pytest.mark.parametrize(
    "builder_type",
    [VariableBuilder, ExpressionBuilder, ConstraintBuilder],
)
def test_builder_keeps_model(builder_type: type[object]) -> None:
    model = cp_model.CpModel()

    builder = builder_type(model)  # type: ignore[call-arg]

    assert builder.model is model  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "builder_type",
    [ExpressionBuilder],
)
def test_builder_build_is_empty(builder_type: type[object]) -> None:
    model = cp_model.CpModel()
    input_ = make_input()
    builder = builder_type(model)  # type: ignore[call-arg]

    result = builder.build(input_)  # type: ignore[attr-defined]

    assert result is None
    assert len(model.Proto().variables) == 0
    assert len(model.Proto().constraints) == 0


def test_variable_builder_creates_no_variables_for_empty_input() -> None:
    model = cp_model.CpModel()

    variables = VariableBuilder(model).build(make_input())

    assert len(variables) == 0
    assert len(model.Proto().variables) == 0


def test_variable_builder_creates_one_boolean_per_person_and_cell() -> None:
    model = cp_model.CpModel()
    input_ = MurdokuInput(
        map=Map(
            cells=(
                Cell(latitude=0, longitude=0, room="comedor"),
                Cell(latitude=0, longitude=1, room="cocina"),
                Cell(latitude=1, longitude=1, room="cocina"),
            )
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(),
    )

    variables = VariableBuilder(model).build(input_)

    assert set(variables) == {
        (name, latitude, longitude)
        for name in ("Alice", "Bob")
        for latitude, longitude in ((0, 0), (0, 1), (1, 1))
    }
    assert len(model.Proto().variables) == 6
    for proto_variable in model.Proto().variables:
        assert list(proto_variable.domain) == [0, 1]


def test_model_builder_exposes_variables() -> None:
    input_ = MurdokuInput(
        map=Map(cells=(Cell(latitude=0, longitude=0, room="comedor"),)),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(),
    )

    optimization_model = ModelBuilder().build(input_)

    assert set(optimization_model.variables) == {("Alice", 0, 0)}


def test_model_builder_creates_empty_optimization_model() -> None:
    input_ = make_input()

    optimization_model = ModelBuilder().build(input_)

    assert isinstance(optimization_model, OptimizationModel)
    assert optimization_model.input is input_
    assert len(optimization_model.model.Proto().variables) == 0
    assert len(optimization_model.model.Proto().constraints) == 0


def test_optimization_model_solve_counts_solutions() -> None:
    optimization_model = ModelBuilder().build(make_input())
    model = optimization_model.model
    x = model.new_bool_var("x")
    y = model.new_bool_var("y")
    model.add(x + y == 1)

    assert optimization_model.solve() == 2


def test_optimization_model_solve_stops_at_max_solutions() -> None:
    optimization_model = ModelBuilder().build(make_input())
    for index in range(4):
        optimization_model.model.new_bool_var(f"x{index}")

    assert optimization_model.solve() == 2
    assert optimization_model.solve(max_solutions=3) == 3
    assert optimization_model.solve(max_solutions=None) == 16


def test_optimization_model_solve_returns_zero_when_infeasible() -> None:
    optimization_model = ModelBuilder().build(make_input())
    variable = optimization_model.model.new_bool_var("x")
    optimization_model.model.add(variable == 1)
    optimization_model.model.add(variable == 0)

    assert optimization_model.solve() == 0


def test_solution_result_retains_valid_placement_and_stops_after_two() -> None:
    input_ = make_grid_input(((0, 0), (0, 1), (1, 0), (1, 1)))
    optimization_model = ModelBuilder().build(input_)

    result = optimization_model.solve_with_solution()

    assert result.count == 2
    assert result.first_solution is not None
    assert set(result.first_solution) == {"Alice", "Bob"}
    alice = result.first_solution["Alice"]
    bob = result.first_solution["Bob"]
    assert alice[0] != bob[0]
    assert alice[1] != bob[1]
    assert input_.map.get_cell(*alice) is not None
    assert input_.map.get_cell(*bob) is not None
    assert optimization_model.solve(max_solutions=None) == 4
    with pytest.raises(TypeError):
        result.first_solution["Alice"] = (9, 9)  # type: ignore[index]


def test_solution_result_for_infeasible_model_has_no_placement() -> None:
    optimization_model = ModelBuilder().build(make_grid_input(((0, 0),)))

    result = optimization_model.solve_with_solution()

    assert result.count == 0
    assert result.first_solution is None


def test_empty_model_has_one_empty_placement() -> None:
    result = ModelBuilder().build(make_input()).solve_with_solution()

    assert result.count == 1
    assert result.first_solution == {}


def test_solution_counter_keeps_first_placement_not_last() -> None:
    model = cp_model.CpModel()
    variables = {
        ("Alice", 0, 0): model.new_bool_var("first"),
        ("Alice", 1, 1): model.new_bool_var("second"),
    }
    counter = _SolutionCounter(variables, max_solutions=None)
    with patch.object(counter, "boolean_value", side_effect=[True, False]):
        counter.on_solution_callback()
    with patch.object(counter, "boolean_value") as boolean_value:
        counter.on_solution_callback()
        boolean_value.assert_not_called()

    assert counter.count == 2
    assert counter.first_solution == {"Alice": (0, 0)}


def test_model_builder_executes_each_builder() -> None:
    input_ = make_input()

    with (
        patch(
            "murdoku_checker.optimization.model_builder.VariableBuilder"
        ) as variables,
        patch(
            "murdoku_checker.optimization.model_builder.ExpressionBuilder"
        ) as expressions,
        patch(
            "murdoku_checker.optimization.model_builder.ConstraintBuilder"
        ) as constraints,
    ):
        optimization_model = ModelBuilder().build(input_)

    assert variables.call_args == call(optimization_model.model)
    assert expressions.call_args == call(optimization_model.model)
    assert constraints.call_args == call(optimization_model.model)
    variables.return_value.build.assert_called_once_with(input_)
    expressions.return_value.build.assert_called_once_with(input_)
    constraints.return_value.build.assert_called_once_with(
        input_, variables.return_value.build.return_value
    )


def make_grid_input(positions: tuple[tuple[int, int], ...]) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                Cell(latitude=latitude, longitude=longitude, room="comedor")
                for latitude, longitude in positions
            )
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(),
    )


def count_solutions(
    positions: tuple[tuple[int, int], ...], *constraint_methods: str
) -> int:
    input_ = make_grid_input(positions)
    model = cp_model.CpModel()
    variables = VariableBuilder(model).build(input_)
    builder = ConstraintBuilder(model)
    for method in constraint_methods:
        if method == "build_person_constraints":
            builder.build_person_constraints(input_, variables)
        else:
            getattr(builder, method)(variables)
    return OptimizationModel(input_, model, variables).solve(max_solutions=None)


def test_row_constraints_allow_at_most_one_person_per_row() -> None:
    # Same row: only one of the 4 variables can be true -> empty + 4 singles.
    assert count_solutions(((0, 0), (0, 1)), "build_row_constraints") == 5
    # Different rows: each row has its own limit -> (1 + 2) * (1 + 2).
    assert count_solutions(((0, 0), (1, 0)), "build_row_constraints") == 9


def test_column_constraints_allow_at_most_one_person_per_column() -> None:
    assert count_solutions(((0, 0), (1, 0)), "build_column_constraints") == 5
    assert count_solutions(((0, 0), (0, 1)), "build_column_constraints") == 9


def test_person_constraints_place_each_person_in_exactly_one_cell() -> None:
    # 2 people, 2 cells: each one picks a cell independently.
    assert count_solutions(((0, 0), (0, 1)), "build_person_constraints") == 4


def test_constraint_builder_build_executes_all_constraints() -> None:
    positions = ((0, 0), (0, 1), (1, 0), (1, 1))
    input_ = make_grid_input(positions)
    model = cp_model.CpModel()
    variables = VariableBuilder(model).build(input_)

    ConstraintBuilder(model).build(input_, variables)

    # 2 people + 2 rows + 2 columns.
    assert len(model.Proto().constraints) == 6
    # Alice picks any of 4 cells; Bob must take the opposite diagonal cell.
    assert OptimizationModel(input_, model, variables).solve(max_solutions=None) == 4


def make_next_to_input(rules: tuple[Rule, ...]) -> MurdokuInput:
    #  (0,0) box/a   (0,1) a   (0,2) b
    #  (1,0) a       (1,1) b   (1,2) b
    cells = (
        Cell(latitude=0, longitude=0, room="a", features=(CellFeature.BOX,)),
        Cell(latitude=0, longitude=1, room="a"),
        Cell(latitude=0, longitude=2, room="b"),
        Cell(latitude=1, longitude=0, room="a"),
        Cell(latitude=1, longitude=1, room="b", features=(CellFeature.PLANT,)),
        Cell(latitude=1, longitude=2, room="b"),
    )
    return MurdokuInput(
        map=Map(cells=cells),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(rules=rules),
    )


def box_rule() -> Rule:
    return Rule(
        person="Alice",
        condition=NextTo(element=FeatureElement(value=CellFeature.BOX)),
    )


def test_variable_builder_next_to_keeps_adjacent_cells_in_same_room() -> None:
    input_ = make_next_to_input((box_rule(),))

    variables = VariableBuilder(cp_model.CpModel()).build(input_)

    assert set(variables) == {("Alice", 0, 1), ("Alice", 1, 0)}


def test_variable_builder_next_to_ignores_adjacent_cells_in_other_rooms() -> None:
    rule = Rule(
        person="Alice",
        condition=NextTo(element=FeatureElement(value=CellFeature.PLANT)),
    )

    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input((rule,)))

    assert set(variables) == {("Alice", 1, 2)}


@pytest.mark.parametrize(
    ("feature", "expected"),
    [
        (CellFeature.BOX, {("Alice", 0, 2), ("Alice", 1, 2)}),
        (
            CellFeature.PLANT,
            {("Alice", 0, 1), ("Alice", 0, 2), ("Alice", 1, 0)},
        ),
    ],
)
def test_not_next_to_is_exact_complement_on_occupiable_cells(
    feature: CellFeature, expected: set[tuple[str, int, int]]
) -> None:
    element = FeatureElement(value=feature)
    positive = Rule(person="Alice", condition=NextTo(element=element))
    negative = Rule(person="Alice", condition=NotNextTo(element=element))
    builder = VariableBuilder(cp_model.CpModel())

    next_to = set(builder.build(make_next_to_input((positive,))))
    not_next_to = set(builder.build(make_next_to_input((negative,))))
    unrestricted = set(builder.build(make_next_to_input(())))

    assert not_next_to == expected
    assert next_to.isdisjoint(not_next_to)
    assert next_to | not_next_to == unrestricted
    model = ModelBuilder().build(make_next_to_input((negative,)))
    assert model.solve(max_solutions=None) == len(expected)


def test_next_to_and_not_next_to_are_contradictory_but_any_of_is_tautology() -> None:
    positive = box_rule()
    negative = Rule(
        person="Alice",
        condition=NotNextTo(element=FeatureElement(value=CellFeature.BOX)),
    )

    model = ModelBuilder().build(make_next_to_input((positive, negative)))
    assert model.solve(max_solutions=None) == 0

    either = Rule(
        person="Alice",
        condition=AnyOf(conditions=(positive.condition, negative.condition)),
    )
    model = ModelBuilder().build(make_next_to_input((either,)))
    assert model.solve(max_solutions=None) == 4


def test_not_next_to_intersects_with_room_rule() -> None:
    rules = (
        Rule(
            person="Alice",
            condition=NotNextTo(element=FeatureElement(value=CellFeature.PLANT)),
        ),
        Rule(person="Alice", condition=In(element=RoomElement(value="b"))),
    )
    model = ModelBuilder().build(make_next_to_input(rules))

    assert set(model.variables) == {("Alice", 0, 2)}
    assert model.solve_with_solution().first_solution == {"Alice": (0, 2)}


def test_not_next_to_checks_every_feature_and_allows_diagonals_and_feature_cells() -> (
    None
):
    cells = tuple(
        Cell(
            latitude=row,
            longitude=column,
            room="a",
            features=(
                (CellFeature.CHAIR,)
                if (row, column) in {(0, 0), (0, 2)}
                else (CellFeature.BOX,)
                if (row, column) == (2, 2)
                else ()
            ),
        )
        for row in range(3)
        for column in range(3)
    )
    input_ = MurdokuInput(
        map=Map(cells=cells),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(
            rules=(
                Rule(
                    person="Alice",
                    condition=NotNextTo(
                        element=FeatureElement(value=CellFeature.CHAIR)
                    ),
                ),
            )
        ),
    )
    model = ModelBuilder().build(input_)

    assert set(model.variables) == {
        ("Alice", 0, 0),
        ("Alice", 0, 2),
        ("Alice", 1, 1),
        ("Alice", 2, 0),
        ("Alice", 2, 1),
    }
    assert model.solve(max_solutions=None) == 5


def test_variable_builder_any_of_unites_next_to_cells() -> None:
    rule = Rule(
        person="Alice",
        condition=AnyOf(
            conditions=(
                NextTo(element=FeatureElement(value=CellFeature.BOX)),
                NextTo(element=FeatureElement(value=CellFeature.PLANT)),
            )
        ),
    )

    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input((rule,)))

    assert set(variables) == {
        ("Alice", 0, 1),
        ("Alice", 1, 0),
        ("Alice", 1, 2),
    }


def test_variable_builder_skips_non_occupiable_cells() -> None:
    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input(()))

    assert set(variables) == {
        ("Alice", 0, 1),
        ("Alice", 0, 2),
        ("Alice", 1, 0),
        ("Alice", 1, 2),
    }


def test_variable_builder_in_room_keeps_only_occupiable_room_cells() -> None:
    rule = Rule(person="Alice", condition=In(element=RoomElement(value="b")))

    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input((rule,)))

    assert set(variables) == {("Alice", 0, 2), ("Alice", 1, 2)}


def test_variable_builder_in_feature_keeps_cells_with_feature() -> None:
    rule = Rule(
        person="Alice",
        condition=In(element=FeatureElement(value=CellFeature.BED)),
    )
    cells = (
        Cell(latitude=0, longitude=0, room="a", features=(CellFeature.BED,)),
        Cell(latitude=0, longitude=1, room="a", features=(CellFeature.BED,)),
        Cell(latitude=1, longitude=0, room="a"),
    )
    input_ = MurdokuInput(
        map=Map(cells=cells),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(rules=(rule,)),
    )

    variables = VariableBuilder(cp_model.CpModel()).build(input_)

    assert set(variables) == {("Alice", 0, 0), ("Alice", 0, 1)}


def test_variable_builder_any_of_unites_in_and_next_to() -> None:
    rule = Rule(
        person="Alice",
        condition=AnyOf(
            conditions=(
                In(element=RoomElement(value="b")),
                NextTo(element=FeatureElement(value=CellFeature.BOX)),
            )
        ),
    )

    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input((rule,)))

    assert set(variables) == {
        ("Alice", 0, 1),
        ("Alice", 0, 2),
        ("Alice", 1, 0),
        ("Alice", 1, 2),
    }


def test_model_without_allowed_cells_is_infeasible() -> None:
    plant_rule = Rule(
        person="Alice",
        condition=NextTo(element=FeatureElement(value=CellFeature.PLANT)),
    )
    input_ = make_next_to_input((box_rule(), plant_rule))

    assert len(VariableBuilder(cp_model.CpModel()).build(input_)) == 0
    optimization_model = ModelBuilder().build(input_)

    assert optimization_model.solve(max_solutions=None) == 0
