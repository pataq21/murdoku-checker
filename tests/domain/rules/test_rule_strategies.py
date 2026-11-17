import pytest

from murdoku_checker.domain import (
    AnyOfRule,
    BaseRule,
    CoordinateAxis,
    Direction,
    FeatureElement,
    FeatureTargetRelation,
    GridCell,
    InCoordinateRule,
    InRule,
    Map,
    NextToRule,
    NotNextToRule,
    PersonElement,
    RelativePositionRule,
    RoomElement,
    RoomRelationKind,
    RoomRelationRule,
    Solution,
)

#  (0,0) a/box   (0,1) a       (0,2) b
#  (1,0) a       (1,1) b/plant (1,2) b
MAP = Map(
    cells=(
        GridCell(latitude=0, longitude=0, room="a", features=("box",)),
        GridCell(latitude=0, longitude=1, room="a"),
        GridCell(latitude=0, longitude=2, room="b"),
        GridCell(latitude=1, longitude=0, room="a"),
        GridCell(latitude=1, longitude=1, room="b", features=("plant",)),
        GridCell(latitude=1, longitude=2, room="b"),
    )
)
BOX = FeatureElement(value="box")
PLANT = FeatureElement(value="plant")
BOB = PersonElement(value="Bob")


def solve(alice: tuple[int, int], bob: tuple[int, int]) -> Solution:
    return Solution(map=MAP, placements={"Alice": alice, "Bob": bob})


@pytest.mark.parametrize(
    ("rule", "description"),
    [
        (NextToRule(person="Alice", element=BOX), "Alice is next to a box."),
        (
            NotNextToRule(person="Alice", element=BOX),
            "Alice is not next to any box.",
        ),
        (InRule(person="Alice", element=RoomElement(value="a")), "Alice is in the a."),
        (
            InRule(person="Alice", element=PLANT, is_unique=True),
            "Alice is the only person on a plant.",
        ),
        (
            InCoordinateRule(person="Alice", axis=CoordinateAxis.COLUMN, value=0),
            "Alice is in column 1.",
        ),
        (
            RelativePositionRule(person="Alice", direction=Direction.NORTH, element=BOB),
            "Alice is somewhere north of Bob.",
        ),
        (
            RelativePositionRule(
                person="Alice",
                direction=Direction.EAST,
                element=PLANT,
                offset=2,
                feature_relation=FeatureTargetRelation.NEXT_TO,
            ),
            "Alice is exactly 2 columns east of a person next to a plant.",
        ),
        (
            RoomRelationRule(
                person="Alice", relation=RoomRelationKind.DIFFERENT, element=BOB
            ),
            "Alice is in a different room from Bob.",
        ),
        (
            AnyOfRule(
                person="Alice",
                conditions=(
                    NextToRule(person="Alice", element=BOX),
                    AnyOfRule(
                        person="Alice",
                        conditions=(
                            NextToRule(person="Alice", element=PLANT),
                            InRule(person="Alice", element=RoomElement(value="b")),
                        ),
                    ),
                ),
            ),
            (
                "Either Alice is next to a box or Alice is next to a plant "
                "or Alice is in the b."
            ),
        ),
    ],
)
def test_description_is_readable_clue(rule: BaseRule, description: str) -> None:
    assert rule.description == description


def test_difficulty_grows_with_cognitive_cost() -> None:
    in_room = InRule(person="Alice", element=RoomElement(value="a"))
    same_room = RoomRelationRule(
        person="Alice", relation=RoomRelationKind.SAME, element=BOB
    )
    north = RelativePositionRule(person="Alice", direction=Direction.NORTH, element=BOB)
    either = AnyOfRule(person="Alice", conditions=(in_room, north))

    assert in_room.difficulty < same_room.difficulty < north.difficulty
    assert either.difficulty > in_room.difficulty + north.difficulty


def test_only_the_clause_subject_is_a_protagonist() -> None:
    next_to = NextToRule(person="Alice", element=BOX)
    north = RelativePositionRule(person="Alice", direction=Direction.NORTH, element=BOB)
    same_room = RoomRelationRule(
        person="Alice", relation=RoomRelationKind.SAME, element=BOB
    )

    for rule in (
        next_to, north, same_room,
        AnyOfRule(person="Alice", conditions=(next_to, north)),
    ):
        assert rule.protagonists == {"Alice"}
    assert north.targets == (BOB,)
    assert same_room.targets == (BOB,)


@pytest.mark.parametrize(
    ("rule", "alice", "bob", "expected"),
    [
        (NextToRule(person="Alice", element=BOX), (0, 1), (1, 2), True),
        # Diagonal cells and cells of another room are not adjacent.
        (NextToRule(person="Alice", element=PLANT), (0, 1), (1, 0), False),
        (NotNextToRule(person="Alice", element=PLANT), (0, 1), (1, 0), True),
        (NotNextToRule(person="Alice", element=PLANT), (1, 2), (0, 0), False),
        (InRule(person="Alice", element=RoomElement(value="b")), (0, 2), (1, 1), True),
        (
            InRule(person="Alice", element=RoomElement(value="b"), is_unique=True),
            (0, 2),
            (1, 1),
            False,
        ),
        (
            InRule(person="Alice", element=RoomElement(value="b"), is_unique=True),
            (0, 2),
            (1, 0),
            True,
        ),
        (
            InCoordinateRule(person="Alice", axis=CoordinateAxis.ROW, value=1),
            (1, 2),
            (0, 0),
            True,
        ),
        (
            RelativePositionRule(person="Alice", direction=Direction.WEST, element=BOB),
            (1, 0),
            (0, 2),
            True,
        ),
        (
            RelativePositionRule(
                person="Alice", direction=Direction.WEST, element=BOB, offset=1
            ),
            (1, 0),
            (0, 2),
            False,
        ),
        (
            RelativePositionRule(
                person="Alice",
                direction=Direction.NORTH,
                element=PersonElement(value="Alice"),
            ),
            (0, 1),
            (1, 0),
            False,
        ),
        # A feature target needs somebody else standing on the feature.
        (
            RelativePositionRule(person="Alice", direction=Direction.SOUTH, element=BOX),
            (1, 2),
            (0, 0),
            True,
        ),
        (
            RelativePositionRule(person="Alice", direction=Direction.SOUTH, element=BOX),
            (1, 2),
            (0, 1),
            False,
        ),
        (
            RoomRelationRule(
                person="Alice", relation=RoomRelationKind.SAME, element=BOB
            ),
            (0, 1),
            (1, 0),
            True,
        ),
        (
            RoomRelationRule(
                person="Alice", relation=RoomRelationKind.DIFFERENT, element=BOB
            ),
            (0, 1),
            (1, 0),
            False,
        ),
        (
            AnyOfRule(
                person="Alice",
                conditions=(
                    NextToRule(person="Alice", element=PLANT),
                    InRule(person="Alice", element=RoomElement(value="a")),
                ),
            ),
            (0, 1),
            (1, 2),
            True,
        ),
        (
            AnyOfRule(
                person="Alice",
                conditions=(
                    NextToRule(person="Alice", element=PLANT),
                    InRule(person="Alice", element=RoomElement(value="a")),
                ),
            ),
            (0, 2),
            (1, 0),
            False,
        ),
    ],
)
def test_evaluate_checks_rule_on_solution(
    rule: BaseRule,
    alice: tuple[int, int],
    bob: tuple[int, int],
    expected: bool,
) -> None:
    assert rule.evaluate(solve(alice, bob)) is expected
