import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOf,
    Cell,
    Direction,
    Element,
    Elements,
    FeatureElement,
    Gender,
    In,
    Map,
    MurdokuInput,
    NextTo,
    NotNextTo,
    People,
    Person,
    PersonElement,
    RelativePosition,
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
            Rule(
                person="Alex",
                condition=In(element=RoomElement(value="comedor")),
            ),
            Rule(
                person="Alex",
                condition=NextTo(element=FeatureElement(value="plant")),
            ),
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
            Rule(
                person="Unknown",
                condition=In(element=RoomElement(value="comedor")),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown person in rule: Unknown"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


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
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


@pytest.mark.parametrize("condition_type", [NextTo, NotNextTo])
@pytest.mark.parametrize("nested", [False, True])
def test_murdoku_input_rejects_unknown_feature(
    condition_type: type[NextTo] | type[NotNextTo], nested: bool
) -> None:
    condition = condition_type(element=FeatureElement(value="box"))
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=(
                    AnyOf(
                        conditions=(
                            In(element=RoomElement(value="comedor")),
                            condition,
                        )
                    )
                    if nested
                    else condition
                ),
            )
        ]
    )

    with pytest.raises(ValidationError, match="unknown feature in rule: box"):
        MurdokuInput(
            map=make_map(), elements=make_elements(), people=make_people(), rules=rules
        )


def test_murdoku_input_validates_nested_any_of_references() -> None:
    rules = Rules(
        rules=[
            Rule(
                person="Alex",
                condition=AnyOf(
                    conditions=[
                        NextTo(element=FeatureElement(value="plant")),
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
    relative = RelativePosition(
        direction=Direction.SOUTH, element=PersonElement(value="Cameron")
    )
    rules = Rules(
        rules=(
            Rule(
                person="Alex",
                condition=(
                    AnyOf(
                        conditions=(
                            In(element=RoomElement(value="comedor")),
                            AnyOf(conditions=(relative, relative)),
                        )
                    )
                    if nested
                    else relative
                ),
            ),
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
