import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOfRule,
    Direction,
    Element,
    Elements,
    FeatureElement,
    Gender,
    GridCell,
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
    Rules,
)


def make_map() -> Map:
    return Map(
        cells=[
            GridCell(
                latitude=0,
                longitude=0,
                room="comedor",
                features=["plant"],
            )
        ]
    )


def make_people() -> People:
    return People(people=[Person(name="Alex", gender=Gender.MALE)])


def make_elements() -> Elements:
    return Elements(elements=(Element(name="plant"),))


def test_murdoku_input_accepts_consistent_references() -> None:
    rules = Rules(
        rules=[
            InRule(person="Alex", element=RoomElement(value="comedor")),
            NextToRule(person="Alex", element=FeatureElement(value="plant")),
        ]
    )

    input_ = MurdokuInput(
        map=make_map(), elements=make_elements(), people=make_people(), rules=rules
    )

    assert input_.rules is rules


def test_murdoku_input_accepts_empty_rules() -> None:
    input_ = MurdokuInput(
        map=make_map(), elements=make_elements(), people=make_people(), rules=Rules()
    )

    assert input_.rules.rules == ()


def test_murdoku_input_rejects_map_element_missing_from_catalog() -> None:
    with pytest.raises(ValidationError, match="unknown element in map: plant"):
        MurdokuInput(
            map=make_map(),
            elements=Elements(),
            people=make_people(),
            rules=Rules(),
        )


@pytest.mark.parametrize(
    ("is_occupiable", "expected"),
    [(False, False), (True, True)],
)
def test_murdoku_input_resolves_cell_occupancy_from_catalog(
    is_occupiable: bool, expected: bool
) -> None:
    input_ = MurdokuInput(
        map=make_map(),
        elements=Elements(
            elements=(Element(name="plant", is_occupiable=is_occupiable),)
        ),
        people=make_people(),
        rules=Rules(),
    )

    assert input_.is_cell_occupiable(input_.map.cells[0]) is expected


def test_murdoku_input_rejects_unknown_person() -> None:
    rules = Rules(
        rules=[
            InRule(person="Unknown", element=RoomElement(value="comedor"))
        ]
    )

    with pytest.raises(ValidationError, match="unknown person in rule: Unknown"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


def test_murdoku_input_rejects_unknown_room() -> None:
    rules = Rules(
        rules=[
            InRule(person="Alex", element=RoomElement(value="dormitorio"))
        ]
    )

    with pytest.raises(ValidationError, match="unknown room in rule: dormitorio"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


@pytest.mark.parametrize("rule_type", [NextToRule, NotNextToRule])
@pytest.mark.parametrize("nested", [False, True])
def test_murdoku_input_rejects_unknown_feature(
    rule_type: type[NextToRule] | type[NotNextToRule], nested: bool
) -> None:
    rule = rule_type(person="Alex", element=FeatureElement(value="box"))
    rules = Rules(
        rules=[
            AnyOfRule(
                person="Alex",
                conditions=(
                    InRule(person="Alex", element=RoomElement(value="comedor")),
                    rule,
                ),
            )
            if nested
            else rule
        ]
    )

    with pytest.raises(ValidationError, match="unknown feature in rule: box"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


def test_murdoku_input_validates_nested_any_of_references() -> None:
    rules = Rules(
        rules=[
            AnyOfRule(
                person="Alex",
                conditions=[
                    NextToRule(person="Alex", element=FeatureElement(value="plant")),
                    AnyOfRule(
                        person="Alex",
                        conditions=[
                            InRule(person="Alex", element=RoomElement(value="comedor")),
                            InRule(
                                person="Alex", element=RoomElement(value="dormitorio")
                            ),
                        ],
                    ),
                ],
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown room in rule: dormitorio"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


def test_murdoku_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        MurdokuInput(
            map=make_map(),
            elements=make_elements(),
            people=make_people(),
            rules=Rules(),
            name="invalid",  # type: ignore[call-arg]
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_murdoku_input_is_immutable() -> None:
    input_ = MurdokuInput(
        map=make_map(), elements=make_elements(), people=make_people(), rules=Rules()
    )

    with pytest.raises(ValidationError) as error:
        input_.rules = Rules()

    assert error.value.errors()[0]["type"] == "frozen_instance"


@pytest.mark.parametrize("nested", [False, True])
def test_relative_position_references_must_exist(nested: bool) -> None:
    relative = RelativePositionRule(
        person="Alex", direction=Direction.SOUTH, element=PersonElement(value="Cameron")
    )
    rules = Rules(
        rules=(
            AnyOfRule(
                person="Alex",
                conditions=(
                    InRule(person="Alex", element=RoomElement(value="comedor")),
                    AnyOfRule(person="Alex", conditions=(relative, relative)),
                ),
            )
            if nested
            else relative,
        )
    )

    with pytest.raises(ValidationError, match="unknown person in rule: Cameron"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )

    people = People(
        people=(*make_people().people, Person(name="Cameron", gender=Gender.FEMALE))
    )
    assert (
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=people, rules=rules
        ).rules
        is rules
    )
