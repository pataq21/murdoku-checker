import json

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    RULE_ADAPTER,
    AnyOfRule,
    BaseRule,
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
)


def parse(person: str, condition: dict[str, object]) -> BaseRule:
    return RULE_ADAPTER.validate_json(
        json.dumps({"person": person, "condition": condition})
    )


def test_base_rule_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseRule(person="Alex")  # type: ignore[abstract]


@pytest.mark.parametrize("rule_type", [NextToRule, NotNextToRule])
def test_adjacency_rule_from_json(
    rule_type: type[NextToRule] | type[NotNextToRule],
) -> None:
    rule_type_name = rule_type.model_fields["type"].default
    rule = parse(
        "Alexander",
        {"type": rule_type_name, "element": {"type": "feature", "value": "box"}},
    )

    assert rule == rule_type(person="Alexander", element=FeatureElement(value="box"))


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        ({"type": "room", "value": "dormitorio"}, RoomElement),
        ({"type": "feature", "value": "chair"}, FeatureElement),
    ],
)
def test_in_rule_validates_elements_from_json(
    element: dict[str, str], expected: type[RoomElement] | type[FeatureElement]
) -> None:
    rule = parse("Dalia", {"type": "in", "element": element})

    assert isinstance(rule, InRule)
    assert rule.person == "Dalia"
    assert isinstance(rule.element, expected)
    assert rule.is_unique is False


def test_in_rule_accepts_unique_flag() -> None:
    rule = parse(
        "Carol",
        {
            "type": "in",
            "element": {"type": "feature", "value": "carpet"},
            "is_unique": True,
        },
    )

    assert isinstance(rule, InRule)
    assert rule.is_unique is True


@pytest.mark.parametrize("axis", list(CoordinateAxis))
def test_in_coordinate_round_trips_json(axis: CoordinateAxis) -> None:
    rule = parse("Corinne", {"type": "in_coordinate", "axis": axis.value, "value": 4})

    assert rule == InCoordinateRule(person="Corinne", axis=axis, value=4)
    assert RULE_ADAPTER.validate_json(RULE_ADAPTER.dump_json(rule)) == rule


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
        RULE_ADAPTER.validate_python(
            {"person": "Corinne", "condition": condition}, strict=True
        )


def test_nested_any_of_from_json_inherits_person() -> None:
    rule = RULE_ADAPTER.validate_json(
        '{"person":"Evangeline","condition":{"type":"any_of","conditions":['
        '{"type":"next_to","element":{"type":"feature","value":"tree"}},'
        '{"type":"any_of","conditions":['
        '{"type":"next_to","element":{"type":"feature","value":"plant"}},'
        '{"type":"in","element":{"type":"room","value":"comedor"}}]}'
        "]}}"
    )

    assert isinstance(rule, AnyOfRule)
    first, nested = rule.conditions
    assert isinstance(first, NextToRule)
    assert isinstance(nested, AnyOfRule)
    assert isinstance(nested.conditions[1], InRule)
    assert {first.person, nested.person, nested.conditions[1].person} == {
        "Evangeline"
    }


def test_any_of_requires_at_least_two_conditions() -> None:
    with pytest.raises(ValidationError) as error:
        AnyOfRule(
            person="Alex",
            conditions=[NextToRule(person="Alex", element=FeatureElement(value="x"))],
        )

    assert error.value.errors()[0]["type"] == "too_short"


def test_any_of_rejects_conditions_of_another_person() -> None:
    with pytest.raises(ValidationError, match="must refer to the same person"):
        AnyOfRule(
            person="Alex",
            conditions=[
                NextToRule(person="Alex", element=FeatureElement(value="x")),
                NextToRule(person="Bob", element=FeatureElement(value="y")),
            ],
        )


@pytest.mark.parametrize("condition_type", ["next_to", "not_next_to"])
def test_adjacency_rejects_room_element(condition_type: str) -> None:
    with pytest.raises(ValidationError) as error:
        parse(
            "Alex",
            {"type": condition_type, "element": {"type": "room", "value": "comedor"}},
        )

    assert error.value.errors()[0]["loc"][-1] == "type"


def test_rule_rejects_unknown_condition_type() -> None:
    with pytest.raises(ValidationError) as error:
        RULE_ADAPTER.validate_python({"person": "Alex", "condition": {"type": "unknown"}})

    assert error.value.errors()[0]["type"] == "union_tag_invalid"


def test_rule_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        RULE_ADAPTER.validate_python(
            {
                "person": "Alex",
                "condition": {
                    "type": "next_to",
                    "element": {"type": "feature", "value": "plant"},
                },
                "note": "invalid",
            }
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("rule_type", [NextToRule, NotNextToRule])
def test_rule_dumps_rules_json_shape_and_round_trips(
    rule_type: type[NextToRule] | type[NotNextToRule],
) -> None:
    rule = AnyOfRule(
        person="Evangeline",
        conditions=[
            rule_type(person="Evangeline", element=FeatureElement(value="tree")),
            NextToRule(person="Evangeline", element=FeatureElement(value="plant")),
        ],
    )

    dumped = json.loads(RULE_ADAPTER.dump_json(rule))

    assert dumped == {
        "person": "Evangeline",
        "condition": {
            "type": "any_of",
            "conditions": [
                {
                    "type": rule_type.model_fields["type"].default,
                    "element": {"type": "feature", "value": "tree"},
                },
                {
                    "type": "next_to",
                    "element": {"type": "feature", "value": "plant"},
                },
            ],
        },
    }
    assert RULE_ADAPTER.validate_json(RULE_ADAPTER.dump_json(rule)) == rule


def test_rule_is_immutable() -> None:
    rule = NextToRule(person="Alex", element=FeatureElement(value="plant"))

    with pytest.raises(ValidationError) as error:
        rule.person = "Bob"

    assert error.value.errors()[0]["type"] == "frozen_instance"


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_round_trips_json(direction: Direction) -> None:
    rule = parse(
        "Brigitte",
        {
            "type": "relative_position",
            "direction": direction.value,
            "element": {"type": "person", "value": "Cameron"},
        },
    )

    assert isinstance(rule, RelativePositionRule)
    assert rule.direction is direction
    assert rule.element == PersonElement(value="Cameron")
    assert rule.offset is None
    assert RULE_ADAPTER.validate_json(RULE_ADAPTER.dump_json(rule)) == rule


@pytest.mark.parametrize("direction", list(Direction))
def test_relative_position_accepts_exact_offset(direction: Direction) -> None:
    rule = RelativePositionRule(
        person="Brandon",
        direction=direction,
        element=PersonElement(value="Donovan"),
        offset=1,
    )

    assert rule.offset == 1
    assert RULE_ADAPTER.validate_json(RULE_ADAPTER.dump_json(rule)) == rule


def test_relative_position_accepts_feature_target() -> None:
    rule = RelativePositionRule(
        person="Carissa",
        direction=Direction.WEST,
        element=FeatureElement(value="car"),
        offset=3,
    )

    assert rule.element == FeatureElement(value="car")
    assert rule.feature_relation is FeatureTargetRelation.IN


def test_relative_position_accepts_next_to_feature_target() -> None:
    rule = RelativePositionRule(
        person="Kimberly",
        direction=Direction.NORTH,
        element=FeatureElement(value="statue"),
        offset=2,
        feature_relation=FeatureTargetRelation.NEXT_TO,
    )

    assert rule.feature_relation is FeatureTargetRelation.NEXT_TO


def test_relative_position_rejects_feature_relation_for_person() -> None:
    with pytest.raises(
        ValidationError, match="feature_relation requires a feature element"
    ):
        RelativePositionRule(
            person="Kimberly",
            direction=Direction.NORTH,
            element=PersonElement(value="Iliana"),
            feature_relation=FeatureTargetRelation.NEXT_TO,
        )


@pytest.mark.parametrize("offset", [0, -1])
def test_relative_position_rejects_non_positive_offset(offset: int) -> None:
    with pytest.raises(ValidationError):
        RelativePositionRule(
            person="Brandon",
            direction=Direction.SOUTH,
            element=PersonElement(value="Donovan"),
            offset=offset,
        )


@pytest.mark.parametrize("relation", list(RoomRelationKind))
def test_room_relation_round_trips_json(relation: RoomRelationKind) -> None:
    rule = RoomRelationRule(
        person="Brandon",
        relation=relation,
        element=PersonElement(value="Donovan"),
    )

    assert RULE_ADAPTER.validate_json(RULE_ADAPTER.dump_json(rule)) == rule


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
        parse("Brigitte", condition)
