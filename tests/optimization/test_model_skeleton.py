from unittest.mock import call, patch

import pytest
from ortools.sat.python import cp_model

from murdoku_checker.domain import Map, MurdokuInput, People, Rules
from murdoku_checker.domain.cell import Cell
from murdoku_checker.domain.person import Gender, Person
from murdoku_checker.optimization import ModelBuilder, OptimizationModel
from murdoku_checker.optimization.constraint_builder import ConstraintBuilder
from murdoku_checker.optimization.expression_builder import ExpressionBuilder
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
