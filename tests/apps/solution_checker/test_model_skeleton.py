from unittest.mock import call, patch

import pytest
from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_checker import ModelBuilder, OptimizationModel
from murdoku_checker.apps.solution_checker.constraint_builder import ConstraintBuilder
from murdoku_checker.apps.solution_checker.model import _SolutionCounter
from murdoku_checker.apps.solution_checker.variable_builder import VariableBuilder
from murdoku_checker.domain import (
    AnyOfRule,
    Element,
    Elements,
    FeatureElement,
    GridCell,
    InRule,
    Map,
    MurdokuInput,
    NextToRule,
    NotNextToRule,
    People,
    RoomElement,
    Rules,
)
from murdoku_checker.domain.person import Gender, Person
from murdoku_checker.domain.rules import BaseRule

TEST_ELEMENTS = Elements(
    elements=(
        Element(name="bed", is_occupiable=True),
        Element(name="box"),
        Element(name="carpet", is_occupiable=True),
        Element(name="chair", is_occupiable=True),
        Element(name="plant"),
    )
)


def make_input() -> MurdokuInput:
    return MurdokuInput(
        map=Map(), elements=TEST_ELEMENTS, people=People(), rules=Rules()
    )


class _PlacementCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, optimization_model: OptimizationModel) -> None:
        super().__init__()
        self._variables = optimization_model.variables
        self.placements: set[tuple[str, int, int]] = set()

    def on_solution_callback(self) -> None:
        self.placements.update(
            key
            for key, variable in self._variables.items()
            if self.boolean_value(variable)
        )


def feasible_placements(input_: MurdokuInput) -> set[tuple[str, int, int]]:
    """(person, latitude, longitude) triples used by at least one solution."""
    optimization_model = ModelBuilder().build(input_)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    collector = _PlacementCollector(optimization_model)
    solver.solve(optimization_model.model, collector)
    return collector.placements


@pytest.mark.parametrize("builder_type", [VariableBuilder, ConstraintBuilder])
def test_builder_keeps_model(builder_type: type[object]) -> None:
    model = cp_model.CpModel()

    builder = builder_type(model)  # type: ignore[call-arg]

    assert builder.model is model  # type: ignore[attr-defined]


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
                GridCell(latitude=0, longitude=0, room="comedor"),
                GridCell(latitude=0, longitude=1, room="cocina"),
                GridCell(latitude=1, longitude=1, room="cocina"),
            )
        ),
        elements=TEST_ELEMENTS,
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
        map=Map(cells=(GridCell(latitude=0, longitude=0, room="comedor"),)),
        elements=TEST_ELEMENTS,
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
            "murdoku_checker.apps.solution_checker.model_builder.VariableBuilder"
        ) as variables,
        patch(
            "murdoku_checker.apps.solution_checker.model_builder.ConstraintBuilder"
        ) as constraints,
    ):
        optimization_model = ModelBuilder().build(input_)

    assert variables.call_args == call(optimization_model.model)
    assert constraints.call_args == call(optimization_model.model)
    variables.return_value.build.assert_called_once_with(input_)
    constraints.return_value.build.assert_called_once_with(
        input_, variables.return_value.build.return_value
    )


def make_grid_input(positions: tuple[tuple[int, int], ...]) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                GridCell(latitude=latitude, longitude=longitude, room="comedor")
                for latitude, longitude in positions
            )
        ),
        elements=TEST_ELEMENTS,
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


def make_next_to_input(rules: tuple[BaseRule, ...]) -> MurdokuInput:
    #  (0,0) box/a   (0,1) a   (0,2) b
    #  (1,0) a       (1,1) b   (1,2) b
    cells = (
        GridCell(latitude=0, longitude=0, room="a", features=("box",)),
        GridCell(latitude=0, longitude=1, room="a"),
        GridCell(latitude=0, longitude=2, room="b"),
        GridCell(latitude=1, longitude=0, room="a"),
        GridCell(latitude=1, longitude=1, room="b", features=("plant",)),
        GridCell(latitude=1, longitude=2, room="b"),
    )
    return MurdokuInput(
        map=Map(cells=cells),
        elements=TEST_ELEMENTS,
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(rules=rules),
    )


def box_rule() -> NextToRule:
    return NextToRule(person="Alice", element=FeatureElement(value="box"))


def test_next_to_keeps_adjacent_cells_in_same_room() -> None:
    assert feasible_placements(make_next_to_input((box_rule(),))) == {
        ("Alice", 0, 1),
        ("Alice", 1, 0),
    }


def test_next_to_ignores_adjacent_cells_in_other_rooms() -> None:
    rule = NextToRule(person="Alice", element=FeatureElement(value="plant"))

    assert feasible_placements(make_next_to_input((rule,))) == {("Alice", 1, 2)}


@pytest.mark.parametrize(
    ("feature", "expected"),
    [
        ("box", {("Alice", 0, 2), ("Alice", 1, 2)}),
        (
            "plant",
            {("Alice", 0, 1), ("Alice", 0, 2), ("Alice", 1, 0)},
        ),
    ],
)
def test_not_next_to_is_exact_complement_on_occupiable_cells(
    feature: str, expected: set[tuple[str, int, int]]
) -> None:
    element = FeatureElement(value=feature)
    positive = NextToRule(person="Alice", element=element)
    negative = NotNextToRule(person="Alice", element=element)

    next_to = feasible_placements(make_next_to_input((positive,)))
    not_next_to = feasible_placements(make_next_to_input((negative,)))
    unrestricted = feasible_placements(make_next_to_input(()))

    assert not_next_to == expected
    assert next_to.isdisjoint(not_next_to)
    assert next_to | not_next_to == unrestricted
    model = ModelBuilder().build(make_next_to_input((negative,)))
    assert model.solve(max_solutions=None) == len(expected)


def test_next_to_and_not_next_to_are_contradictory_but_any_of_is_tautology() -> None:
    positive = box_rule()
    negative = NotNextToRule(person="Alice", element=FeatureElement(value="box"))

    model = ModelBuilder().build(make_next_to_input((positive, negative)))
    assert model.solve(max_solutions=None) == 0

    either = AnyOfRule(person="Alice", conditions=(positive, negative))
    model = ModelBuilder().build(make_next_to_input((either,)))
    assert model.solve(max_solutions=None) == 4


def test_not_next_to_intersects_with_room_rule() -> None:
    rules = (
        NotNextToRule(person="Alice", element=FeatureElement(value="plant")),
        InRule(person="Alice", element=RoomElement(value="b")),
    )
    model = ModelBuilder().build(make_next_to_input(rules))

    assert model.solve_with_solution().first_solution == {"Alice": (0, 2)}
    assert model.solve(max_solutions=None) == 1


def test_not_next_to_checks_every_feature_and_allows_diagonals_and_feature_cells() -> (
    None
):
    cells = tuple(
        GridCell(
            latitude=row,
            longitude=column,
            room="a",
            features=(
                ("chair",)
                if (row, column) in {(0, 0), (0, 2)}
                else ("box",)
                if (row, column) == (2, 2)
                else ()
            ),
        )
        for row in range(3)
        for column in range(3)
    )
    input_ = MurdokuInput(
        map=Map(cells=cells),
        elements=TEST_ELEMENTS,
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(
            rules=(
                NotNextToRule(person="Alice", element=FeatureElement(value="chair")),
            )
        ),
    )

    assert feasible_placements(input_) == {
        ("Alice", 0, 0),
        ("Alice", 0, 2),
        ("Alice", 1, 1),
        ("Alice", 2, 0),
        ("Alice", 2, 1),
    }
    assert ModelBuilder().build(input_).solve(max_solutions=None) == 5


def test_any_of_unites_next_to_cells() -> None:
    rule = AnyOfRule(
        person="Alice",
        conditions=(
            NextToRule(person="Alice", element=FeatureElement(value="box")),
            NextToRule(person="Alice", element=FeatureElement(value="plant")),
        ),
    )

    assert feasible_placements(make_next_to_input((rule,))) == {
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


def test_variable_builder_ignores_rules() -> None:
    rule = InRule(person="Alice", element=RoomElement(value="b"))

    variables = VariableBuilder(cp_model.CpModel()).build(make_next_to_input((rule,)))

    assert len(variables) == 4


def test_in_room_keeps_only_occupiable_room_cells() -> None:
    rule = InRule(person="Alice", element=RoomElement(value="b"))

    assert feasible_placements(make_next_to_input((rule,))) == {
        ("Alice", 0, 2),
        ("Alice", 1, 2),
    }


def test_in_feature_keeps_cells_with_feature() -> None:
    rule = InRule(person="Alice", element=FeatureElement(value="bed"))
    cells = (
        GridCell(latitude=0, longitude=0, room="a", features=("bed",)),
        GridCell(latitude=0, longitude=1, room="a", features=("bed",)),
        GridCell(latitude=1, longitude=0, room="a"),
    )
    input_ = MurdokuInput(
        map=Map(cells=cells),
        elements=TEST_ELEMENTS,
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(rules=(rule,)),
    )

    assert feasible_placements(input_) == {("Alice", 0, 0), ("Alice", 0, 1)}


def test_any_of_unites_in_and_next_to() -> None:
    rule = AnyOfRule(
        person="Alice",
        conditions=(
            InRule(person="Alice", element=RoomElement(value="b")),
            NextToRule(person="Alice", element=FeatureElement(value="box")),
        ),
    )

    assert feasible_placements(make_next_to_input((rule,))) == {
        ("Alice", 0, 1),
        ("Alice", 0, 2),
        ("Alice", 1, 0),
        ("Alice", 1, 2),
    }


def test_model_without_allowed_cells_is_infeasible() -> None:
    plant_rule = NextToRule(person="Alice", element=FeatureElement(value="plant"))
    input_ = make_next_to_input((box_rule(), plant_rule))

    assert ModelBuilder().build(input_).solve(max_solutions=None) == 0
