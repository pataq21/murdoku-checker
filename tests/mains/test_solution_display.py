from murdoku_checker.domain import (
    Element,
    ElementSpecification,
    Elements,
    FurniturePlacement,
    GeneratedSolution,
    GenerationConfig,
    GenerationSpecification,
    Gender,
    GridCell,
    Map,
    MurdokuInput,
    People,
    Person,
    Rules,
    Solution,
)
from murdoku_checker.mains.solution_display import (
    format_generated_solution,
    format_solution,
)


def test_grid_shows_coordinates_rooms_obstacles_and_missing_cells() -> None:
    input_ = MurdokuInput(
        map=Map(
            cells=(
                GridCell(latitude=8, longitude=9, room="comedor"),
                GridCell(
                    latitude=2,
                    longitude=5,
                    room="cocina",
                    features=("plant",),
                ),
                GridCell(latitude=2, longitude=9, room="comedor"),
            )
        ),
        elements=Elements(elements=(Element(name="plant"),)),
        people=People(people=(Person(name="Alice", gender=Gender.FEMALE),)),
        rules=Rules(),
    )

    assert format_solution(input_, {"Alice": (8, 9)}) == (
        "First solution (rows = latitude, columns = longitude):\n"
        "      5       9\n"
        "2 | #/R1  | ./R2  |\n"
        "8 |       | P1/R2 |\n"
        "\n"
        "Legend:\n"
        "  . = unoccupied cell; # = blocked cell; blank = no cell\n"
        "  P1 = Alice (latitude=8, longitude=9)\n"
        "  R1 = cocina\n"
        "  R2 = comedor"
    )


def test_grid_ids_remain_distinct_and_aligned_with_long_names_and_coordinates() -> None:
    names = [f"Alex with a very long name {index}" for index in range(12)]
    input_ = MurdokuInput(
        map=Map(
            cells=tuple(
                GridCell(latitude=index, longitude=1000 + index, room=f"room {index:02}")
                for index in range(12)
            )
        ),
        people=People(
            people=tuple(Person(name=name, gender=Gender.MALE) for name in names)
        ),
        rules=Rules(),
    )
    solution = {name: (index, 1000 + index) for index, name in enumerate(names)}

    output = format_solution(input_, solution)
    rows = output.splitlines()[2:14]

    assert len({len(row) for row in rows}) == 1
    assert all(row.count("|") == 13 for row in rows)
    assert "P12/R12" in rows[-1]
    assert "1011" in output.splitlines()[1]
    assert "P12 = Alex with a very long name 11 (latitude=11, longitude=1011)" in output


def test_grid_without_people_still_shows_map() -> None:
    input_ = MurdokuInput(
        map=Map(cells=(GridCell(latitude=0, longitude=0, room="comedor"),)),
        people=People(),
        rules=Rules(),
    )

    output = format_solution(input_, {})

    assert "0 | ./R1 |" in output
    assert "R1 = comedor" in output
    assert "P1" not in output


def test_grid_for_empty_map() -> None:
    input_ = MurdokuInput(map=Map(), people=People(), rules=Rules())

    assert format_solution(input_, {}) == "First solution: empty map."


def test_generated_grid_shows_people_rooms_and_blocked_cells() -> None:
    specification = GenerationSpecification(
        config=GenerationConfig(
            rows=2,
            columns=3,
            element_coverage_percent=33,
            element_type_count=2,
            room_count=1,
        ),
        elements=(
            ElementSpecification(Element(name="rock"), 1, 1),
            ElementSpecification(
                Element(name="carpet", is_occupiable=True), 1, 1
            ),
        ),
    )
    generated = GeneratedSolution(
        specification=specification,
        solution=Solution(
            map=Map(
                cells=(
                    GridCell(
                        latitude=0, longitude=0, room="room_1", features=("rock",)
                    ),
                    GridCell(
                        latitude=0, longitude=1, room="room_1", features=("carpet",)
                    ),
                    GridCell(latitude=0, longitude=2, room="room_1"),
                    GridCell(latitude=1, longitude=0, room="room_1"),
                    GridCell(latitude=1, longitude=1, room="room_1"),
                    GridCell(latitude=1, longitude=2, room="room_1"),
                )
            ),
            placements={"person_1": (0, 2), "person_2": (1, 0)},
        ),
        victim="person_2",
        furniture=(
            FurniturePlacement("rock", ((0, 0),)),
            FurniturePlacement("carpet", ((0, 1),)),
        ),
    )

    output = format_generated_solution(generated)

    assert output.startswith("Generated solution (rows = latitude")
    assert "#/R1" in output
    assert "./R1" in output
    assert "P2*/R1" in output
    assert "P1 = person_1 (latitude=0, longitude=2)" in output
    assert "P2* = person_2 (victim) (latitude=1, longitude=0)" in output
    assert "* = victim" in output
    assert "R1 = room_1" in output
