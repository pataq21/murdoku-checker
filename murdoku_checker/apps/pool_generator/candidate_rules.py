from collections.abc import Iterator
from itertools import combinations

from murdoku_checker.domain import (
    AnyOfRule,
    CoordinateAxis,
    Direction,
    FeatureElement,
    FeatureTargetRelation,
    InCoordinateRule,
    InRule,
    NextToRule,
    NotNextToRule,
    PersonElement,
    RelativePositionRule,
    RoomElement,
    RoomRelationKind,
    RoomRelationRule,
    Rule,
    Solution,
)


def _iter_simple_rules(solution: Solution, person: str) -> Iterator[Rule]:
    features = tuple(
        FeatureElement(value=name)
        for name in sorted(
            {feature for cell in solution.map.cells for feature in cell.features}
        )
    )
    rooms = tuple(RoomElement(value=room.name) for room in solution.map.rooms)
    others = tuple(
        PersonElement(value=name)
        for name in sorted(solution.placements)
        if name != person
    )

    for element in (*rooms, *features):
        for is_unique in (False, True):
            yield InRule(person=person, element=element, is_unique=is_unique)

    for feature in features:
        yield NextToRule(person=person, element=feature)
        yield NotNextToRule(person=person, element=feature)

    coordinates = {
        CoordinateAxis.ROW: sorted(
            {row for row, _ in solution.map.positions}
        ),
        CoordinateAxis.COLUMN: sorted(
            {column for _, column in solution.map.positions}
        ),
    }
    for axis, values in coordinates.items():
        for value in values:
            yield InCoordinateRule(person=person, axis=axis, value=value)

    for other in others:
        for relation in RoomRelationKind:
            yield RoomRelationRule(person=person, element=other, relation=relation)

    offsets = {
        axis: sorted({second - first for first, second in combinations(values, 2)})
        for axis, values in coordinates.items()
    }
    for element in (*others, *features):
        relations = (
            tuple(FeatureTargetRelation)
            if isinstance(element, FeatureElement)
            else (FeatureTargetRelation.IN,)
        )
        for direction in Direction:
            axis = (
                CoordinateAxis.ROW
                if direction in (Direction.NORTH, Direction.SOUTH)
                else CoordinateAxis.COLUMN
            )
            for offset in (None, *offsets[axis]):
                for relation in relations:
                    yield RelativePositionRule(
                        person=person,
                        element=element,
                        direction=direction,
                        offset=offset,
                        feature_relation=relation,
                    )


def iter_candidate_rules(solution: Solution) -> Iterator[Rule]:
    """Enumerate simple clues and unordered, unnested pairs per person.

    Targets and exact offsets come from the map. Truth is deliberately not
    checked here, so disjunctions can contain a false alternative.
    """
    people = sorted(solution.placements)
    for person in people:
        solution.cell_of(person)
    for person in people:
        simple = tuple(_iter_simple_rules(solution, person))
        yield from simple
        for first, second in combinations(simple, 2):
            yield AnyOfRule(person=person, conditions=(first, second))
