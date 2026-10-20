import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOf,
    Cell,
    CellFeature,
    FeatureElement,
    Gender,
    In,
    Map,
    MurdokuInput,
    NextTo,
    People,
    Person,
    RoomElement,
    Rule,
    Rules,
)


def make_map() -> Map:
    return Map(
        cells=[
            Cell(
                latitude=0,
                longitude=0,
                room="comedor",
                features=[CellFeature.PLANT],
            )
        ]
    )


def make_people() -> People:
    return People(people=[Person(name="Alex", gender=Gender.MALE)])


def test_murdoku_input_accepts_consistent_references() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=In(element=RoomElement(value="comedor")),
            ),
            Rule(
                person="Alex",
                condition=NextTo(element=FeatureElement(value=CellFeature.PLANT)),
            ),
        ]
    )

    input_ = MurdokuInput(map=make_map(), people=make_people(), rules=rules)

    assert input_.rules is rules


def test_murdoku_input_accepts_empty_rules() -> None:
    input_ = MurdokuInput(map=make_map(), people=make_people(), rules=Rules())

    assert input_.rules.rules == ()


def test_murdoku_input_rejects_unknown_person() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Unknown",
                condition=In(element=RoomElement(value="comedor")),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown person in rule: Unknown"):
        MurdokuInput(map=make_map(), people=make_people(), rules=rules)


def test_murdoku_input_rejects_unknown_room() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=In(element=RoomElement(value="dormitorio")),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown room in rule: dormitorio"):
        MurdokuInput(map=make_map(), people=make_people(), rules=rules)


def test_murdoku_input_rejects_unknown_feature() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=NextTo(element=FeatureElement(value=CellFeature.BOX)),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown feature in rule: box"):
        MurdokuInput(map=make_map(), people=make_people(), rules=rules)


def test_murdoku_input_validates_nested_any_of_references() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=AnyOf(
                    conditions=[
                        NextTo(element=FeatureElement(value=CellFeature.PLANT)),
                        AnyOf(
                            conditions=[
                                In(element=RoomElement(value="comedor")),
                                In(element=RoomElement(value="dormitorio")),
                            ]
                        ),
                    ]
                ),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown room in rule: dormitorio"):
        MurdokuInput(map=make_map(), people=make_people(), rules=rules)


def test_murdoku_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        MurdokuInput(
            map=make_map(),
            people=make_people(),
            rules=Rules(),
            name="invalid",  # type: ignore[call-arg]
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_murdoku_input_is_immutable() -> None:
    input_ = MurdokuInput(map=make_map(), people=make_people(), rules=Rules())

    with pytest.raises(ValidationError) as error:
        input_.rules = Rules()

    assert error.value.errors()[0]["type"] == "frozen_instance"
