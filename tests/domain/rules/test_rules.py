import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    FeatureElement,
    NextToRule,
    Rules,
)


def make_rule(person: str = "Alex") -> NextToRule:
    return NextToRule(person=person, element=FeatureElement(value="plant"))


def test_rules_can_be_empty() -> None:
    rules = Rules()

    assert rules.rules == ()


def test_rules_stores_rules_as_tuple() -> None:
    first = make_rule("Alex")
    second = make_rule("Bob")

    rules = Rules(rules=[first, second])

    assert rules.rules == (first, second)


def test_rules_rejects_non_rule_items() -> None:
    with pytest.raises(ValidationError) as error:
        Rules(rules=["not a rule"])  # type: ignore[list-item]

    assert error.value.errors()[0]["loc"] == ("rules", 0)


def test_rules_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Rules(rules=(), name="invalid")  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_rules_is_immutable() -> None:
    rules = Rules()

    with pytest.raises(ValidationError) as error:
        rules.rules = ()

    assert error.value.errors()[0]["type"] == "frozen_instance"
