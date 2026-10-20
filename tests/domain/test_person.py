import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Gender, Person


def test_person_defaults_features_to_absent() -> None:
    person = Person(name="Alex", gender=Gender.MALE)

    assert person.name == "Alex"
    assert person.gender is Gender.MALE
    assert person.wear_glasses is False
    assert person.is_bald is False
    assert person.is_victim is False


def test_person_accepts_explicit_features() -> None:
    person = Person(
        name="Alex",
        gender=Gender.FEMALE,
        wear_glasses=True,
        is_bald=True,
        is_victim=True,
    )

    assert person.wear_glasses
    assert person.is_bald
    assert person.is_victim


def test_person_rejects_empty_name() -> None:
    with pytest.raises(ValidationError) as error:
        Person(name="", gender=Gender.MALE)

    assert error.value.errors()[0]["type"] == "string_too_short"


def test_person_rejects_non_string_name() -> None:
    with pytest.raises(ValidationError) as error:
        Person(name=1, gender=Gender.MALE)  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "string_type"


@pytest.mark.parametrize("gender", ["Male", "Female", "Other"])
def test_person_rejects_string_gender_in_python(gender: str) -> None:
    with pytest.raises(ValidationError) as error:
        Person(name="Alex", gender=gender)  # type: ignore[arg-type]

    assert error.value.errors()[0]["type"] == "is_instance_of"


def test_person_serializes_gender_value_to_json() -> None:
    person = Person(name="Alex", gender=Gender.FEMALE)

    assert person.model_dump_json() == (
        '{"name":"Alex","gender":"Female","wear_glasses":false,'
        '"is_bald":false,"is_victim":false}'
    )


def test_person_validates_gender_value_from_json() -> None:
    person = Person.model_validate_json('{"name":"Alex","gender":"Male"}')

    assert person.gender is Gender.MALE


def test_person_rejects_unknown_gender_from_json() -> None:
    with pytest.raises(ValidationError) as error:
        Person.model_validate_json('{"name":"Alex","gender":"Other"}')

    assert error.value.errors()[0]["type"] == "enum"


@pytest.mark.parametrize("feature", ["wear_glasses", "is_bald", "is_victim"])
def test_person_rejects_non_boolean_features(feature: str) -> None:
    with pytest.raises(ValidationError) as error:
        Person.model_validate({"name": "Alex", "gender": Gender.MALE, feature: 1})

    assert error.value.errors()[0]["type"] == "bool_type"


def test_person_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as error:
        Person(name="Alex", gender=Gender.MALE, age=30)  # type: ignore[call-arg]

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_person_is_immutable() -> None:
    person = Person(name="Alex", gender=Gender.MALE)

    with pytest.raises(ValidationError) as error:
        person.is_bald = True

    assert error.value.errors()[0]["type"] == "frozen_instance"
