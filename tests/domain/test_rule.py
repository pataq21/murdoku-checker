import json

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOf,
    CellFeature,
    FeatureElement,
    In,
    NextTo,
    RoomElement,
    Rule,
)


def test_rule_accepts_next_to_feature() -> None:
    condition = NextTo(element=FeatureElement(value=CellFeature.BOX))

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
                NextTo(element=FeatureElement(value=CellFeature.PLANT)),
            ]
        )

    assert error.value.errors()[0]["type"] == "too_short"


def test_next_to_rejects_room_element() -> None:
    with pytest.raises(ValidationError) as error:
        Rule.model_validate_json(
            '{"person":"Alex","condition":{"type":"next_to",'
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
            condition=NextTo(element=FeatureElement(value=CellFeature.PLANT)),
            note="invalid",  # type: ignore[call-arg]
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_rule_round_trips_json() -> None:
    rule = Rule(
        person="Evangeline",
        condition=AnyOf(
            conditions=[
                NextTo(element=FeatureElement(value=CellFeature.TREE)),
                NextTo(element=FeatureElement(value=CellFeature.PLANT)),
            ]
        ),
    )

    assert Rule.model_validate_json(rule.model_dump_json()) == rule


def test_rule_is_immutable() -> None:
    rule = Rule(
        person="Alex",
        condition=NextTo(element=FeatureElement(value=CellFeature.PLANT)),
    )

    with pytest.raises(ValidationError) as error:
        rule.person = "Bob"

    assert error.value.errors()[0]["type"] == "frozen_instance"
