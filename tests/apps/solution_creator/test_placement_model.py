from collections import Counter
from unittest.mock import patch

import pytest
from ortools.sat.python import cp_model

from murdoku_checker.apps.solution_creator import generate_solution
from murdoku_checker.apps.solution_creator.placement_model import PlacementModel
from murdoku_checker.domain import (
    Element,
    ElementSpecification,
    GeneratedSolution,
    GenerationConfig,
    GenerationSpecification,
)


def make_specification(
    rows: int,
    columns: int,
    rooms: int,
    elements: tuple[ElementSpecification, ...] = (),
    seed: int = 17,
) -> GenerationSpecification:
    occupied = sum(item.size * item.count for item in elements)
    return GenerationSpecification(
        config=GenerationConfig(
            rows=rows,
            columns=columns,
            element_coverage_percent=100 * occupied / (rows * columns),
            element_type_count=len(elements),
            room_count=rooms,
            seed=seed,
        ),
        elements=elements,
    )


def assert_valid_solution(generated: GeneratedSolution) -> None:
    specification = generated.specification
    config = specification.config
    solution = generated.solution
    assert solution.map.positions == frozenset(
        (row, column)
        for row in range(config.rows)
        for column in range(config.columns)
    )
    assert len(solution.map.rooms) == config.room_count
    for room in solution.map.rooms:
        remaining = set(room.positions)
        reached = {remaining.pop()}
        while remaining:
            neighbours = {
                position
                for position in remaining
                if any(
                    abs(position[0] - previous[0])
                    + abs(position[1] - previous[1]) == 1
                    for previous in reached
                )
            }
            assert neighbours, "room is disconnected"
            reached.update(neighbours)
            remaining.difference_update(neighbours)

    types = {item.element.name: item for item in specification.elements}
    assert Counter(item.element for item in generated.furniture) == {
        name: item.count for name, item in types.items()
    }
    occupied: dict[tuple[int, int], str] = {}
    for furniture in generated.furniture:
        assert len(furniture.cells) == types[furniture.element].size
        rooms = set()
        for position in furniture.cells:
            assert position not in occupied, "furniture overlaps"
            occupied[position] = furniture.element
            cell = solution.map.get_cell(*position)
            assert cell is not None
            rooms.add(cell.room)
        assert len(rooms) == 1
        if len(furniture.cells) == 2:
            first, second = furniture.cells
            assert abs(first[0] - second[0]) + abs(first[1] - second[1]) == 1
    assert len(occupied) == config.element_cell_count
    for cell in solution.map.cells:
        assert cell.features == (
            (occupied[cell.position],) if cell.position in occupied else ()
        )

    assert len(solution.placements) == config.person_count
    assert len({row for row, _ in solution.placements.values()}) == config.person_count
    assert len({column for _, column in solution.placements.values()}) == config.person_count
    for person in solution.placements:
        cell = solution.cell_of(person)
        assert all(types[feature].element.is_occupiable for feature in cell.features)
    assert generated.victim == f"person_{config.person_count}"
    victim_room = solution.cell_of(generated.victim).room
    assert sum(
        solution.cell_of(person).room == victim_room
        for person in solution.placements
    ) == 2


@pytest.mark.parametrize(
    ("rows", "columns", "rooms"),
    [(2, 2, 1), (2, 3, 2), (3, 2, 3), (3, 3, 3)],
)
def test_empty_boards_have_connected_nonempty_rooms_and_valid_people(
    rows: int, columns: int, rooms: int
) -> None:
    generated = generate_solution(make_specification(rows, columns, rooms))

    assert generated is not None
    assert_valid_solution(generated)


@pytest.mark.parametrize(
    ("rows", "columns", "rooms"),
    [(1, 1, 1), (1, 5, 3), (5, 1, 3), (2, 3, 6), (3, 3, 1)],
)
def test_reports_impossible_victim_room_requirements(
    rows: int, columns: int, rooms: int
) -> None:
    assert generate_solution(make_specification(rows, columns, rooms)) is None


@pytest.mark.parametrize(
    ("positions", "feasible"),
    [((4, 8, 0), False), ((0, 4, 8), True), ((2, 4, 6), False)],
    ids=["victim-alone", "one-companion", "two-companions"],
)
def test_victim_requires_exactly_one_companion(
    positions: tuple[int, int, int], feasible: bool
) -> None:
    model = PlacementModel(make_specification(3, 3, 2))
    for index, variable in enumerate(model.room_variables):
        model.model.add(variable == (1 if index == 0 else 0))
    for variable, position in zip(model.person_variables, positions, strict=True):
        model.model.add(variable == position)

    generated = model.solve()

    if feasible:
        assert generated is not None
        assert_valid_solution(generated)
    else:
        assert generated is None


def test_other_rooms_can_hold_more_than_two_people() -> None:
    generated = generate_solution(make_specification(5, 5, 2))

    assert generated is not None
    assert_valid_solution(generated)
    counts = Counter(
        generated.solution.cell_of(person).room
        for person in generated.solution.placements
    )
    assert sorted(counts.values()) == [2, 3]


@pytest.mark.parametrize("seed", [0, 17, 99])
def test_places_repeated_furniture_without_changing_the_specification(
    seed: int,
) -> None:
    specification = make_specification(
        3,
        4,
        3,
        (
            ElementSpecification(Element(name="bed", is_occupiable=True), 2, 2),
            ElementSpecification(Element(name="rock"), 1, 3),
        ),
        seed=seed,
    )
    generated = generate_solution(specification)

    assert generated is not None
    assert generated.specification is specification
    assert_valid_solution(generated)
    assert generate_solution(specification) == generated


@pytest.mark.parametrize("occupiable", [False, True])
def test_full_furniture_coverage_allows_people_only_when_occupiable(
    occupiable: bool,
) -> None:
    specification = make_specification(
        2,
        2,
        1,
        (ElementSpecification(Element(name="carpet", is_occupiable=occupiable), 2, 2),),
    )
    generated = generate_solution(specification)

    if occupiable:
        assert generated is not None
        assert_valid_solution(generated)
    else:
        assert generated is None


@pytest.mark.parametrize("positions", [(0, 1), (0, 2)])
def test_rejects_people_sharing_a_row_or_column(
    positions: tuple[int, int],
) -> None:
    model = PlacementModel(make_specification(2, 2, 1))
    for variable, position in zip(model.person_variables, positions, strict=True):
        model.model.add(variable == position)

    assert model.solve() is None


def test_rejects_diagonally_connected_rooms() -> None:
    model = PlacementModel(make_specification(2, 2, 2))
    for variable, room in zip(
        model.room_variables, (0, 1, 1, 0), strict=True
    ):
        model.model.add(variable == room)

    assert model.solve() is None


def test_accepts_connected_nonrectangular_rooms() -> None:
    model = PlacementModel(make_specification(2, 2, 2))
    for variable, room in zip(
        model.room_variables, (0, 0, 0, 1), strict=True
    ):
        model.model.add(variable == room)

    generated = model.solve()
    assert generated is not None
    assert_valid_solution(generated)


def test_furniture_cannot_cross_rooms() -> None:
    specification = make_specification(
        2,
        3,
        3,
        (ElementSpecification(Element(name="bed", is_occupiable=True), 2, 1),),
    )
    model = PlacementModel(specification)
    for variable, room in zip(
        model.room_variables, (0, 0, 1, 0, 0, 2), strict=True
    ):
        model.model.add(variable == room)
    model.model.add(
        sum(
            option.selected for option in model.furniture_options
            if 2 in option.cells
        ) == 1
    )

    assert model.solve() is None


def test_furniture_cannot_overlap_to_make_space_for_extra_rooms() -> None:
    specification = make_specification(
        2,
        3,
        3,
        (ElementSpecification(Element(name="bed", is_occupiable=True), 2, 3),),
    )
    model = PlacementModel(specification)
    for variable, room in zip(
        model.room_variables, (0, 0, 1, 0, 2, 1), strict=True
    ):
        model.model.add(variable == room)

    assert model.solve() is None


def test_size_two_furniture_cannot_use_diagonal_vacancies() -> None:
    specification = make_specification(
        2, 2, 1, (ElementSpecification(Element(name="bed"), 2, 1),)
    )
    model = PlacementModel(specification)
    model.model.add(model.person_variables[0] == 0)
    model.model.add(model.person_variables[1] == 3)

    assert model.solve() is None


@pytest.mark.parametrize(("rows", "columns"), [(2, 3), (3, 2)])
def test_size_two_furniture_fits_both_orientations(
    rows: int, columns: int
) -> None:
    model = PlacementModel(
        make_specification(
            rows,
            columns,
            1,
            (ElementSpecification(Element(name="bed"), 2, 1),),
        )
    )
    footprint = (0, 1) if rows == 2 else (0, columns)
    option = next(
        option for option in model.furniture_options if option.cells == footprint
    )
    model.model.add(option.selected == 1)
    generated = model.solve()

    assert generated is not None
    assert_valid_solution(generated)


@pytest.mark.parametrize("status", [cp_model.UNKNOWN, cp_model.MODEL_INVALID])
def test_inconclusive_solver_status_is_not_reported_as_infeasible(
    status: cp_model.CpSolverStatus,
) -> None:
    with patch.object(cp_model.CpSolver, "solve", return_value=status):
        with pytest.raises(RuntimeError, match="without a conclusive result"):
            generate_solution(make_specification(1, 1, 1))
