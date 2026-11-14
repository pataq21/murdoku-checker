import pytest

from murdoku_checker.apps.solution_checker import ModelBuilder
from murdoku_checker.domain import (
    AnyOfRule,
    BaseRule,
    CoordinateAxis,
    Direction,
    Gender,
    GridCell,
    InCoordinateRule,
    Map,
    MurdokuInput,
    People,
    Person,
    PersonElement,
    RelativePositionRule,
    Rules,
)


def make_input(rule: BaseRule) -> MurdokuInput:
    return MurdokuInput(
        map=Map(
            cells=tuple(
                GridCell(latitude=row, longitude=column, room="playa")
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
        rules=Rules(rules=(rule,)),
    )


@pytest.mark.parametrize(
    ("axis", "value", "expected"),
    [
        (CoordinateAxis.ROW, 1, {(1, 0), (1, 1), (1, 2)}),
        (CoordinateAxis.COLUMN, 2, {(0, 2), (1, 2), (2, 2)}),
    ],
)
def test_in_coordinate_restricts_person_to_line(
    axis: CoordinateAxis, value: int, expected: set[tuple[int, int]]
) -> None:
    rule = InCoordinateRule(person="Alice", axis=axis, value=value)
    model = ModelBuilder().build(make_input(rule))

    result = model.solve_with_solution(max_solutions=None)

    assert result.first_solution is not None
    assert result.first_solution["Alice"] in expected
    # Alice takes one of the 3 cells; Bob any of the 4 cells left by her row
    # and column.
    assert result.count == 3 * 4


def test_in_coordinate_works_in_any_of_with_relative_position() -> None:
    condition = AnyOfRule(
        person="Alice",
        conditions=(
            InCoordinateRule(person="Alice", axis=CoordinateAxis.COLUMN, value=2),
            RelativePositionRule(
                person="Alice",
                direction=Direction.NORTH,
                element=PersonElement(value="Bob"),
            ),
        ),
    )

    model = ModelBuilder().build(make_input(condition))

    assert model.solve(max_solutions=None) == 24
