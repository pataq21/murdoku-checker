from murdoku_checker.domain import (
    Cell,
    Direction,
    Element,
    Elements,
    FeatureElement,
    FeatureTargetRelation,
    Gender,
    Map,
    MurdokuInput,
    People,
    Person,
    RelativePosition,
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

