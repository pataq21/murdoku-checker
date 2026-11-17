from itertools import permutations
from pathlib import Path

import pytest

from murdoku_checker.apps.solution_checker import ModelBuilder, check_solutions
from murdoku_checker.domain import (
    AnyOfRule,
    BaseRule,
    CoordinateAxis,
    Direction,
    Element,
    Elements,
    FeatureElement,
    FeatureTargetRelation,
    Gender,
    GridCell,
    InCoordinateRule,
    InRule,
    Map,
    MurdokuInput,
    NextToRule,
    NotNextToRule,
    People,
    Person,
    PersonElement,
    RelativePositionRule,
    RoomElement,
    RoomRelationKind,
    RoomRelationRule,
    Rules,
    Solution,
)
from murdoku_checker.mains.loaders import (
    load_elements,
    load_map,
    load_people,
    load_rules,
)

FEATURES = {(0, 0): ("box",), (1, 1): ("plant",), (2, 2): ("carpet",)}
MAP = Map(
    cells=tuple(
        GridCell(
            latitude=row,
            longitude=column,
            room="a" if row < 2 and column < 2 else "b",
            features=FEATURES.get((row, column), ()),
        )
        for row in range(3)
        for column in range(3)
    )
)
ELEMENTS = Elements(
    elements=(
        Element(name="box"),
        Element(name="plant", is_occupiable=True),
        Element(name="carpet", is_occupiable=True),
    )
)
PEOPLE = ("Alice", "Bob")
BOB = PersonElement(value="Bob")
PLANT = FeatureElement(value="plant")
CARPET = FeatureElement(value="carpet")

RULES: list[BaseRule] = [
    NextToRule(person="Alice", element=PLANT),
    NotNextToRule(person="Alice", element=FeatureElement(value="box")),
    InRule(person="Alice", element=RoomElement(value="a")),
    InRule(person="Alice", element=RoomElement(value="b"), is_unique=True),
    InRule(person="Alice", element=CARPET, is_unique=True),
    InCoordinateRule(person="Alice", axis=CoordinateAxis.COLUMN, value=1),
    RelativePositionRule(person="Alice", direction=Direction.NORTH, element=BOB),
    RelativePositionRule(
        person="Alice", direction=Direction.EAST, element=BOB, offset=2
    ),
    RelativePositionRule(
        person="Alice", direction=Direction.WEST, element=CARPET, offset=2
    ),
    RelativePositionRule(
        person="Alice",
        direction=Direction.SOUTH,
        element=PLANT,
        feature_relation=FeatureTargetRelation.NEXT_TO,
    ),
    RoomRelationRule(person="Alice", relation=RoomRelationKind.SAME, element=BOB),
    RoomRelationRule(
        person="Alice", relation=RoomRelationKind.DIFFERENT, element=BOB
    ),
    AnyOfRule(
        person="Alice",
        conditions=(
            InRule(person="Alice", element=RoomElement(value="a"), is_unique=True),
            AnyOfRule(
                person="Alice",
                conditions=(
                    RelativePositionRule(
                        person="Alice", direction=Direction.SOUTH, element=BOB
                    ),
                    NextToRule(person="Alice", element=PLANT),
                ),
            ),
        ),
    ),
]


def make_input(rule: BaseRule) -> MurdokuInput:
    return MurdokuInput(
        map=MAP,
        elements=ELEMENTS,
        people=People(
            people=tuple(Person(name=name, gender=Gender.FEMALE) for name in PEOPLE)
        ),
        rules=Rules(rules=(rule,)),
    )


def valid_solutions(input_: MurdokuInput) -> list[Solution]:
    """Placements meeting the occupancy, row and column constraints."""
    cells = [cell.position for cell in MAP.cells if input_.is_cell_occupiable(cell)]
    return [
        Solution(map=MAP, placements=dict(zip(PEOPLE, positions)))
        for positions in permutations(cells, len(PEOPLE))
        if len({row for row, _ in positions}) == len(PEOPLE)
        and len({column for _, column in positions}) == len(PEOPLE)
    ]


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.description)
def test_evaluate_agrees_with_apply_to_model(rule: BaseRule) -> None:
    input_ = make_input(rule)
    expected = sum(rule.evaluate(solution) for solution in valid_solutions(input_))

    result = ModelBuilder().build(input_).solve_with_solution(max_solutions=None)

    assert result.count == expected
    if result.first_solution is not None:
        assert rule.evaluate(Solution(map=MAP, placements=result.first_solution))


@pytest.mark.parametrize(
    "case",
    sorted(
        (Path(__file__).parents[3] / "use_cases" / "verify-puzzle" / "inputs")
        .glob("*/*/rules.json")
    ),
    ids=lambda path: path.parent.name,
)
def test_example_solution_satisfies_every_rule(case: Path) -> None:
    directory = case.parent
    input_ = MurdokuInput(
        map=load_map(directory / "map.json"),
        elements=load_elements(directory / "elements.json"),
        people=load_people(directory / "people.json"),
        rules=load_rules(directory / "rules.json"),
    )

    result = check_solutions(input_)

    assert result.count == 1
    assert result.first_solution is not None
    solution = Solution(map=input_.map, placements=result.first_solution)
    assert all(rule.evaluate(solution) for rule in input_.rules.rules)
