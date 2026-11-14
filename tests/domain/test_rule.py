import json

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOf,
    CoordinateAxis,
    Direction,
    FeatureElement,
    FeatureTargetRelation,
    In,
    InCoordinate,
    NextTo,
    NotNextTo,
    PersonElement,
    RelativePosition,
    RoomRelation,
    RoomRelationKind,
    RoomElement,
    Rule,
)


@pytest.mark.parametrize("condition_type", [NextTo, NotNextTo])
def test_rule_accepts_adjacency_feature(
    condition_type: type[NextTo] | type[NotNextTo],
) -> None:
    condition = condition_type(element=FeatureElement(value="box"))

    rule = Rule(person="Alexander", condition=condition)

    assert rule.person == "Alexander"
    assert rule.condition is condition


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        ({"type": "room", "value": "dormitorio"}, RoomElement),
        ({"type": "feature", "value": "chair"}, FeatureElement),
    ],
)
def test_rule_validates_in_elements_from_json(
    element: dict[str, str], expected: type[RoomElement] | type[FeatureElement]
) -> None:
    rule = Rule.model_validate_json(
        json.dumps(
            {
                "person": "Dalia",
                "condition": {"type": "in", "element": element},
            }
        )
    )

    assert isinstance(rule.condition, In)
    assert isinstance(rule.condition.element, expected)
    assert rule.condition.is_unique is False


def test_rule_accepts_unique_in_condition() -> None:
    rule = Rule.model_validate_json(
        '{"person":"Carol","condition":{"type":"in",'
        '"element":{"type":"feature","value":"carpet"},'
        '"is_unique":true}}'
    )

    assert isinstance(rule.condition, In)
    assert rule.condition.is_unique is True


@pytest.mark.parametrize("axis", list(CoordinateAxis))
def test_in_coordinate_round_trips_json(axis: CoordinateAxis) -> None:
    rule = Rule.model_validate_json(
        json.dumps(
            {
                "person": "Corinne",
                "condition": {
                    "type": "in_coordinate",
                    "axis": axis.value,
                    "value": 4,
                },
            }
        )
    )

    assert rule.condition == InCoordinate(axis=axis, value=4)
    assert Rule.model_validate_json(rule.model_dump_json()) == rule


@pytest.mark.parametrize(
    "condition",
    [
        {"type": "in_coordinate", "axis": "diagonal", "value": 1},
        {"type": "in_coordinate", "axis": "row", "value": -1},
        {"type": "in_coordinate", "axis": "column", "value": "1"},
    ],
)
def test_in_coordinate_rejects_invalid_shape(condition: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Rule.model_validate(
            {"person": "Corinne", "condition": condition}, strict=True
        )


def test_rule_accepts_nested_any_of_from_json() -> None:
    rule = Rule.model_validate_json(
        '{"person":"Evangeline","condition":{"type":"any_of","conditions":['
        '{"type":"next_to","element":{"type":"feature","value":"tree"}},'
        '{"type":"any_of","conditions":['
        '{"type":"next_to","element":{"type":"feature","value":"plant"}},'
        '{"type":"in","element":{"type":"room","value":"comedor"}}]}'
        "]}}"
    )

    assert isinstance(rule.condition, AnyOf)
    assert isinstance(rule.condition.conditions[0], NextTo)
    assert isinstance(rule.condition.conditions[1], AnyOf)


def test_any_of_requires_at_least_two_conditions() -> None:
    with pytest.raises(ValidationError) as error:
        AnyOf(
            conditions=[
                NextTo(element=FeatureElement(value="plant")),
            ]
        )

    assert error.value.errors()[0]["type"] == "too_short"


@pytest.mark.parametrize("condition_type", ["next_to", "not_next_to"])
def test_adjacency_rejects_room_element(condition_type: str) -> None:
    with pytest.raises(ValidationError) as error:
        Rule.model_validate_json(
            '{"person":"Alex","condition":{"type":"' + condition_type + '",'
            '"element":{"type":"room","value":"comedor"}}}'
        )

    assert error.value.errors()[0]["loc"][-1] == "type"


def test_rule_rejects_unknown_condition_type() -> None:
    with pytest.raises(ValidationError) as error:
        Rule.model_validate({"person": "Alex", "condition": {"type": "unknown"}})

    assert error.value.errors()[0]["type"] == "union_tag_invalid"


def test_rule_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Rule(
            person="Alex",
            condition=NextTo(element=FeatureElement(value="plant")),
            note="invalid",  # type: ignore[call-arg]
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("condition_type", [NextTo, NotNextTo])
def test_rule_round_trips_json(
    condition_type: type[NextTo] | type[NotNextTo],
) -> None:
    rule = Rule(
        person="Evangeline",
        condition=AnyOf(
            conditions=[
                condition_type(element=FeatureElement(value="tree")),
                NextTo(element=FeatureElement(value="plant")),
            ]
        ),
    )

    assert Rule.model_validate_json(rule.model_dump_json()) == rule


def test_rule_is_immutable() -> None:
    rule = Rule(
        person="Alex",
        condition=NextTo(element=FeatureElement(value="plant")),
    )

    with pytest.raises(ValidationError) as error:
        rule.person = "Bob"

    assert error.value.errors()[0]["type"] == "frozen_instance"


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_round_trips_json(direction: Direction) -> None:
    rule = Rule.model_validate_json(
        json.dumps(
            {
                "person": "Brigitte",
                "condition": {
                    "type": "relative_position",
                    "direction": direction.value,
                    "element": {"type": "person", "value": "Cameron"},
                },
            }
        )
    )

    assert isinstance(rule.condition, RelativePosition)
    assert rule.condition.direction is direction
    assert rule.condition.element == PersonElement(value="Cameron")
    assert rule.condition.offset is None
    assert Rule.model_validate_json(rule.model_dump_json()) == rule


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_accepts_exact_offset(direction: Direction) -> None:
    condition = RelativePosition(
        direction=direction,
        element=PersonElement(value="Donovan"),
        offset=1,
    )

    assert condition.offset == 1
    assert RelativePosition.model_validate_json(condition.model_dump_json()) == condition


def test_relative_position_accepts_feature_target() -> None:
    condition = RelativePosition(
        direction=Direction.WEST,
        element=FeatureElement(value="car"),
        offset=3,
    )

    assert condition.element == FeatureElement(value="car")
    assert condition.feature_relation is FeatureTargetRelation.IN


def test_relative_position_accepts_next_to_feature_target() -> None:
    condition = RelativePosition(
        direction=Direction.NORTH,
        element=FeatureElement(value="statue"),
        offset=2,
        feature_relation=FeatureTargetRelation.NEXT_TO,
    )

    assert condition.feature_relation is FeatureTargetRelation.NEXT_TO


def test_relative_position_rejects_feature_relation_for_person() -> None:
    with pytest.raises(
        ValidationError, match="feature_relation requires a feature element"
    ):
        RelativePosition(
            direction=Direction.NORTH,
            element=PersonElement(value="Iliana"),
            feature_relation=FeatureTargetRelation.NEXT_TO,
        )


@pytest.mark.parametrize("offset", [0, -1])
def test_relative_position_rejects_non_positive_offset(offset: int) -> None:
    with pytest.raises(ValidationError):
        RelativePosition(
            direction=Direction.SOUTH,
            element=PersonElement(value="Donovan"),
            offset=offset,
        )


@pytest.mark.parametrize("relation", list(RoomRelationKind))
def test_room_relation_round_trips_json(relation: RoomRelationKind) -> None:
    condition = RoomRelation(
        relation=relation,
        element=PersonElement(value="Donovan"),
    )

    assert RoomRelation.model_validate_json(condition.model_dump_json()) == condition


@pytest.mark.parametrize(
    "condition",
    [
        {
            "type": "relative_position",
            "element": {"type": "person", "value": "Cameron"},
        },
        {
            "type": "relative_position",
            "direction": "southwest",
            "element": {"type": "person", "value": "Cameron"},
        },
        {
            "type": "relative_position",
            "direction": "south",
            "element": {"type": "room", "value": "comedor"},
        },
        {
            "type": "relative_position",
            "direction": "south",
            "element": {"type": "person", "value": ""},
        },
        {
            "type": "in",
            "element": {"type": "person", "value": "Cameron"},
        },
    ],
)
def test_relative_position_rejects_invalid_shape(condition: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Rule.model_validate_json(
            json.dumps({"person": "Brigitte", "condition": condition})
        )
