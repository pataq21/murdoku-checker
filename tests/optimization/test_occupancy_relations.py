from murdoku_checker.domain import (
    AloneWith,
    Cell,
    Direction,
    Element,
    Elements,
    FeatureElement,
    FeatureTargetRelation,
    Gender,
    In,
    Map,
    MurdokuInput,
    NextToEmptyRoom,
    OtherRoomOccupied,
    People,
    Person,
    PersonElement,
    RelativePosition,
    RoomElement,
    Rule,
    Rules,
)
from murdoku_checker.optimization import ModelBuilder


def test_relative_position_to_feature_requires_an_occupant_on_feature() -> None:
    input_ = MurdokuInput(
        map=Map(
            cells=tuple(
                Cell(
                    latitude=row,
                    longitude=column,
                    room="calle",
                    features=("car",) if (row, column) == (1, 3) else (),
                )
                for row in range(2)
                for column in range(4)
            )
        ),
        elements=Elements(
            elements=(Element(name="car", is_occupiable=True),)
        ),
        people=People(
            people=(
                Person(name="Carissa", gender=Gender.FEMALE),
                Person(name="Briggs", gender=Gender.MALE),
            )
        ),
        rules=Rules(
            rules=(
                Rule(
                    person="Carissa",
                    condition=RelativePosition(
                        direction=Direction.WEST,
                        element=FeatureElement(value="car"),
                        offset=3,
                    ),
                ),
            )
        ),
    )

    result = ModelBuilder().build(input_).solve_with_solution(max_solutions=None)

    assert result.count == 1
    assert result.first_solution == {"Carissa": (0, 0), "Briggs": (1, 3)}


def test_relative_position_can_target_person_next_to_feature() -> None:
    input_ = MurdokuInput(
        map=Map(
            cells=tuple(
                Cell(
                    latitude=row,
                    longitude=column,
                    room="parque",
                    features=("statue",) if (row, column) == (2, 1) else (),
                )
                for row in range(3)
                for column in range(2)
            )
        ),
        elements=Elements(elements=(Element(name="statue"),)),
        people=People(
            people=(
                Person(name="Kimberly", gender=Gender.FEMALE),
                Person(name="Andy", gender=Gender.MALE),
            )
        ),
        rules=Rules(
            rules=(
                Rule(
                    person="Kimberly",
                    condition=RelativePosition(
                        direction=Direction.NORTH,
                        element=FeatureElement(value="statue"),
                        offset=2,
                        feature_relation=FeatureTargetRelation.NEXT_TO,
                    ),
                ),
            )
        ),
    )

    result = ModelBuilder().build(input_).solve_with_solution(max_solutions=None)

    assert result.count == 1
    assert result.first_solution == {"Kimberly": (0, 1), "Andy": (2, 0)}


def test_alone_with_keeps_companion_and_excludes_everyone_else() -> None:
    input_ = MurdokuInput(
        map=Map(
            cells=(
                Cell(latitude=0, longitude=0, room="a"),
                Cell(latitude=1, longitude=1, room="a"),
                Cell(latitude=2, longitude=2, room="b"),
            )
        ),
        people=People(
            people=(
                Person(name="Andy", gender=Gender.MALE),
                Person(name="Iliana", gender=Gender.FEMALE),
                Person(name="Virgil", gender=Gender.MALE),
            )
        ),
        rules=Rules(
            rules=(
                Rule(
                    person="Andy",
                    condition=AloneWith(
                        element=PersonElement(value="Iliana")
                    ),
                ),
            )
        ),
    )

    result = ModelBuilder().build(input_).solve_with_solution(max_solutions=None)

    assert result.count == 2
    assert result.first_solution is not None
    assert input_.map.get_cell(*result.first_solution["Andy"]).room == "a"  # type: ignore[union-attr]
    assert input_.map.get_cell(*result.first_solution["Iliana"]).room == "a"  # type: ignore[union-attr]
    assert input_.map.get_cell(*result.first_solution["Virgil"]).room == "b"  # type: ignore[union-attr]


def test_next_to_empty_room_requires_an_unoccupied_neighbouring_room() -> None:
    cells = tuple(
        Cell(
            latitude=row,
            longitude=column,
            room=("a", "d", "empty", "c")[column],
        )
        for row in range(3)
        for column in range(4)
    )
    input_ = MurdokuInput(
        map=Map(cells=cells),
        people=People(
            people=(
                Person(name="Donna", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
                Person(name="Carol", gender=Gender.FEMALE),
            )
        ),
        rules=Rules(
            rules=(
                Rule(person="Donna", condition=NextToEmptyRoom()),
                Rule(
                    person="Donna",
                    condition=In(element=RoomElement(value="d")),
                ),
                Rule(
                    person="Bob",
                    condition=In(element=RoomElement(value="a")),
                ),
                Rule(
                    person="Carol",
                    condition=In(element=RoomElement(value="c")),
                ),
            )
        ),
    )

    result = ModelBuilder().build(input_).solve_with_solution()

    assert result.count == 2
    assert result.first_solution is not None
    occupied_rooms = {
        input_.map.get_cell(*position).room  # type: ignore[union-attr]
        for position in result.first_solution.values()
    }
    assert "empty" not in occupied_rooms


def test_other_room_occupied_uses_requested_gender() -> None:
    input_ = MurdokuInput(
        map=Map(
            cells=(
                Cell(latitude=0, longitude=0, room="ascensor_a"),
                Cell(latitude=1, longitude=1, room="ascensor_b"),
                Cell(latitude=2, longitude=2, room="calle"),
            )
        ),
        people=People(
            people=(
                Person(name="Ezra", gender=Gender.MALE),
                Person(name="Allison", gender=Gender.FEMALE),
                Person(name="Virgil", gender=Gender.MALE),
            )
        ),
        rules=Rules(
            rules=(
                Rule(
                    person="Ezra",
                    condition=OtherRoomOccupied(
                        rooms=("ascensor_a", "ascensor_b"),
                        gender=Gender.FEMALE,
                    ),
                ),
            )
        ),
    )

    result = ModelBuilder().build(input_).solve_with_solution(max_solutions=None)

    assert result.count == 2
    assert result.first_solution is not None
    ezra_room = input_.map.get_cell(*result.first_solution["Ezra"]).room  # type: ignore[union-attr]
    allison_room = input_.map.get_cell(*result.first_solution["Allison"]).room  # type: ignore[union-attr]
    assert {ezra_room, allison_room} == {"ascensor_a", "ascensor_b"}
