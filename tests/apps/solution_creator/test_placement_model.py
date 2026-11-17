from collections import Counter
from typing import Literal
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


def make_layout_model(
    layout: tuple[str, ...],
    elements: tuple[ElementSpecification, ...] = (),
) -> PlacementModel:
    names = sorted(set("".join(layout)))
    cells = "".join(layout)
    seeds = tuple(cells.index(name) for name in names)
    with patch.object(PlacementModel, "_choose_room_seeds", return_value=seeds):
        model = PlacementModel(
            make_specification(len(layout), len(layout[0]), len(names), elements)
        )
    for variable, name in zip(model.room_variables, cells, strict=True):
        model.model.add(variable == names.index(name))
    return model


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
    assert sum(
        len({row for row, _ in room.positions}) == 1
        or len({column for _, column in room.positions}) == 1
        for room in solution.map.rooms
    ) <= 1
    for room in solution.map.rooms:
        rows = {row for row, _ in room.positions}
        columns = {column for _, column in room.positions}
        height = max(rows) - min(rows) + 1
        width = max(columns) - min(columns) + 1
        assert 4 * len(room.positions) >= 3 * height * width
        assert 2 * height <= 3 * width
        assert 2 * width <= 3 * height
        for axis in (0, 1):
            for coordinate in {position[axis] for position in room.positions}:
                line = {
                    position[1 - axis]
                    for position in room.positions
                    if position[axis] == coordinate
                }
                assert len(line) == max(line) - min(line) + 1
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
    [(2, 2, 1), (2, 3, 1), (3, 2, 1), (4, 4, 4)],
)
def test_empty_boards_have_connected_nonempty_rooms_and_valid_people(
    rows: int, columns: int, rooms: int
) -> None:
    generated = generate_solution(make_specification(rows, columns, rooms))

    assert generated is not None
    assert_valid_solution(generated)


@pytest.mark.parametrize("count", [0, 1, 3, 4, 5])
@pytest.mark.parametrize("size", [1, 2])
def test_furniture_fills_as_many_rooms_as_possible(
    count: int, size: Literal[1, 2],
) -> None:
    elements = (
        (ElementSpecification(Element(name="table", is_occupiable=True), size, count),)
        if count else ()
    )
    model = make_layout_model(("AABB", "AABB", "CCDD", "CCDD"), elements)

    generated = model.solve()

    assert generated is not None
    assert_valid_solution(generated)
    furnished_rooms = {
        cell.room for cell in generated.solution.map.cells if cell.features
    }
    assert len(furnished_rooms) == min(count, 4)


def test_furniture_preference_allows_a_room_that_cannot_fit_any_piece() -> None:
    model = make_layout_model(
        ("AAABB", "AAABB", "CCXBB", "CCDDD", "CCDDD"),
        (ElementSpecification(Element(name="table", is_occupiable=True), 2, 5),),
    )

    generated = model.solve()

    assert generated is not None
    assert_valid_solution(generated)
    furnished_rooms = {
        cell.room for cell in generated.solution.map.cells if cell.features
    }
    assert len(furnished_rooms) == 4
    singleton = generated.solution.map.get_cell(2, 2)
    assert singleton is not None
    assert singleton.features == ()


@pytest.mark.parametrize(
    ("rows", "columns", "rooms"),
    [(1, 1, 1), (1, 5, 3), (5, 1, 3), (2, 3, 6), (3, 3, 1)],
)
def test_reports_impossible_victim_room_requirements(
    rows: int, columns: int, rooms: int
) -> None:
    assert generate_solution(make_specification(rows, columns, rooms)) is None


@pytest.mark.parametrize(("rows", "columns"), [(2, 3), (3, 2)])
def test_reports_infeasible_room_shapes_without_changing_room_count(
    rows: int, columns: int
) -> None:
    assert generate_solution(make_specification(rows, columns, 3)) is None


@pytest.mark.parametrize(
    ("positions", "feasible"),
    [
        ((0, 7, 20, 28, 35, 15), False),
        ((0, 7, 15, 20, 28, 35), True),
        ((0, 7, 14, 21, 28, 35), False),
    ],
    ids=["victim-alone", "one-companion", "two-companions"],
)
def test_victim_requires_exactly_one_companion(
    positions: tuple[int, ...], feasible: bool
) -> None:
    model = make_layout_model(
        ("AAABBB", "AAABBB", "AAABBB", "CCCDDD", "CCCDDD", "CCCDDD")
    )
    for variable, position in zip(model.person_variables, positions, strict=True):
        model.model.add(variable == position)

    generated = model.solve()

    if feasible:
        assert generated is not None
        assert_valid_solution(generated)
    else:
        assert generated is None


def test_other_rooms_can_hold_more_than_two_people() -> None:
    generated = generate_solution(make_specification(5, 8, 2))

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
        2,
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
    model = make_layout_model(("AB", "BA"))

    assert model.solve() is None


def test_accepts_compact_l_shaped_room() -> None:
    model = make_layout_model(("AA", "AB"))

    generated = model.solve()

    assert generated is not None
    assert_valid_solution(generated)


@pytest.mark.parametrize("transpose", [False, True], ids=["original", "transposed"])
@pytest.mark.parametrize(
    ("layout", "feasible"),
    [
        (("AABB", "AABB", "CCDD", "CCDD"), True),
        (("AAABB", "AAABB", "CCXBB", "CCDDD", "CCDDD"), True),
        (("AAA", "AAA"), True),
        (("AAAA", "AAAA"), False),
        (("AAA", "ABA", "AAA"), False),
        (("AAABB", "AAABB", "CCABB", "CCDDD", "CCDDD"), True),
        (("AAA", "ABB", "ABB"), False),
        (("AAAA", "ABBA", "ABBA", "AAAA"), False),
        (("AAAA", "AAAA", "BBBB", "CCCC"), False),
        (("AAB", "CCB", "CCB"), False),
        (
            (
                "AAABBEEEFF", "AAABBEEEFF", "CCXBBGGYFF",
                "CCDDDGGHHH", "CCDDDGGHHH",
            ),
            False,
        ),
    ],
    ids=[
        "square-rooms", "singleton-counts-once",
        "aspect-ratio-exactly-1.5", "aspect-ratio-above-1.5",
        "hole-in-square-bounding-box",
        "compact-l-shaped-room", "sparse-l-shaped-room",
        "room-with-hole",
        "two-parallel-thin-rooms", "row-and-column-share-one-limit",
        "two-singletons",
    ],
)
def test_room_geometry_constraints(
    layout: tuple[str, ...], feasible: bool, transpose: bool
) -> None:
    if transpose:
        layout = tuple("".join(column) for column in zip(*layout, strict=True))
    model = make_layout_model(layout)

    generated = model.solve()

    assert (generated is not None) is feasible
    if generated is not None:
        assert_valid_solution(generated)


def test_room_seeds_are_repeatable_distinct_and_change_with_seed() -> None:
    first = PlacementModel(make_specification(8, 8, 5, seed=17))
    repeated = PlacementModel(make_specification(8, 8, 5, seed=17))
    other = PlacementModel(make_specification(8, 8, 5, seed=99))

    assert len(set(first.room_seeds)) == 5
    assert first.room_seeds == repeated.room_seeds
    assert first.room_seeds != other.room_seeds


@pytest.mark.parametrize("seed", [0, 17, 99])
def test_generates_local_nonrectangular_rooms_around_fixed_seeds(seed: int) -> None:
    model = PlacementModel(make_specification(8, 8, 5, seed=seed))

    generated = model.solve()

    assert generated is not None
    assert_valid_solution(generated)
    rooms = generated.solution.map.rooms
    assert (
        max(len(room.positions) for room in rooms)
        <= model.specification.config.cell_count // 2
    )
    assert any(
        len(room.positions)
        < len({row for row, _ in room.positions})
        * len({column for _, column in room.positions})
        for room in rooms
    )
    for room, cell in enumerate(model.room_seeds):
        position = model.positions[cell]
        seed_cell = generated.solution.map.get_cell(*position)
        assert seed_cell is not None
        assert seed_cell.room == f"room_{room + 1}"


def test_furniture_cannot_cross_rooms() -> None:
    specification = make_specification(
        4,
        4,
        4,
        (ElementSpecification(Element(name="bed", is_occupiable=True), 2, 1),),
    )
    model = PlacementModel(specification)
    for index, variable in enumerate(model.room_variables):
        row, column = divmod(index, 4)
        model.model.add(variable == (row // 2) * 2 + column // 2)
    crossing = next(
        option for option in model.furniture_options if option.cells == (1, 2)
    )
    model.model.add(crossing.selected == 1)

    assert model.solve() is None


def test_furniture_cannot_overlap() -> None:
    specification = make_specification(
        2,
        2,
        1,
        (ElementSpecification(Element(name="bed", is_occupiable=True), 2, 2),),
    )
    model = PlacementModel(specification)
    for option in model.furniture_options:
        if option.cells == (0, 1):
            model.model.add(option.selected == 1)

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
