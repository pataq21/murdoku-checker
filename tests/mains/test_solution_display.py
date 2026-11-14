from murdoku_checker.domain import (
    GridCell,
    Element,
    Elements,
    Gender,
    Map,
    MurdokuInput,
    People,
    Person,
    Rules,
)
from murdoku_checker.mains.solution_display import format_solution


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
