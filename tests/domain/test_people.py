import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Gender, People, Person


def test_people_can_be_empty() -> None:
    people = People()

    assert people.people == ()


def test_people_stores_persons() -> None:
    first = Person(name="Alice", gender=Gender.FEMALE)
    second = Person(name="Bob", gender=Gender.MALE, wear_glasses=True)

    people = People(people=[first, second])

    assert people.people == (first, second)


def test_people_rejects_duplicate_names() -> None:
    persons = [
        Person(name="Alex", gender=Gender.FEMALE),
        Person(name="Alex", gender=Gender.MALE),
    ]

    with pytest.raises(ValidationError, match="duplicate person name: Alex") as error:
        People(people=persons)

    assert error.value.errors()[0]["loc"] == ("people",)


def test_people_rejects_non_person_items() -> None:
    with pytest.raises(ValidationError) as error:
        People(people=["not a person"])  # type: ignore[list-item]

    assert error.value.errors()[0]["loc"] == ("people", 0)


def test_people_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        People(people=(), name="invalid")  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_people_is_immutable() -> None:
    people = People()

    with pytest.raises(ValidationError) as error:
        people.people = ()  # type: ignore[misc]

    assert error.value.errors()[0]["type"] == "frozen_instance"
