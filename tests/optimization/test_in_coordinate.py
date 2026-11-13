import pytest

from murdoku_checker.domain import (
    AnyOf,
    Cell,
    CoordinateAxis,
    Direction,
    Gender,
    InCoordinate,
    Map,
    MurdokuInput,
    People,
    Person,
    PersonElement,
    RelativePosition,
    Rule,
    Rules,
)
from murdoku_checker.optimization import ModelBuilder


def make_input(condition: InCoordinate | AnyOf) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                Cell(latitude=row, longitude=column, room="playa")
                for row in range(3)
                for column in range(3)
            )
        ),
        people=People(
            people=(
                Person(name="Alice", gender=Gender.FEMALE),
                Person(name="Bob", gender=Gender.MALE),
            )
        ),
        rules=Rules(rules=(Rule(person="Alice", condition=condition),)),
    )


@pytest.mark.parametrize(
    ("axis", "value", "expected"),
    [
        (CoordinateAxis.ROW, 1, {(1, 0), (1, 1), (1, 2)}),
        (CoordinateAxis.COLUMN, 2, {(0, 2), (1, 2), (2, 2)}),
    ],
)
def test_in_coordinate_filters_person_variables(
    axis: CoordinateAxis, value: int, expected: set[tuple[int, int]]
) -> None:
    model = ModelBuilder().build(make_input(InCoordinate(axis=axis, value=value)))

    assert {
        (latitude, longitude)
        for name, latitude, longitude in model.variables
        if name == "Alice"
    } == expected


def test_in_coordinate_works_in_any_of_with_relative_position() -> None:
    condition = AnyOf(
        conditions=(
            InCoordinate(axis=CoordinateAxis.COLUMN, value=2),
            RelativePosition(
                direction=Direction.NORTH,
                element=PersonElement(value="Bob"),
            ),
        )
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 24
