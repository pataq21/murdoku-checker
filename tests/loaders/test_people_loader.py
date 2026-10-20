import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import Gender
from murdoku_checker.loaders import load_people


def write_people(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_people_reads_and_validates_json(tmp_path: Path) -> None:
    path = write_people(
        tmp_path / "people.json",
        {
            "people": [
                {"name": "Alice", "gender": "Female"},
                {"name": "Bob", "gender": "Male", "wear_glasses": True},
            ]
        },
    )

    people = load_people(path)

    assert people.people[0].gender is Gender.FEMALE
    assert people.people[1].wear_glasses is True


def test_load_people_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_people(tmp_path / "missing.json")


def test_load_people_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "people.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        load_people(path)

    assert error.value.errors()[0]["type"] == "json_invalid"


def test_load_people_rejects_invalid_person(tmp_path: Path) -> None:
    path = write_people(
        tmp_path / "people.json",
        {"people": [{"name": "Alice", "gender": "Unknown"}]},
    )

    with pytest.raises(ValidationError) as error:
        load_people(path)

    assert error.value.errors()[0]["loc"] == ("people", 0, "gender")


def test_load_people_rejects_duplicate_names(tmp_path: Path) -> None:
    path = write_people(
        tmp_path / "people.json",
        {
            "people": [
                {"name": "Alex", "gender": "Female"},
                {"name": "Alex", "gender": "Male"},
            ]
        },
    )

    with pytest.raises(ValidationError, match="duplicate person name: Alex"):
        load_people(path)


def test_load_people_rejects_unknown_fields(tmp_path: Path) -> None:
    path = write_people(tmp_path / "people.json", {"people": [], "name": "invalid"})

    with pytest.raises(ValidationError) as error:
        load_people(path)

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_load_example_people() -> None:
    project_root = Path(__file__).parents[2]

    people = load_people(project_root / "inputs" / "example" / "people.json")

    assert [person.name for person in people.people] == [
        "Alexander",
        "Bella",
        "Carol",
        "Dalia",
        "Evangeline",
        "Viraj",
    ]
    assert people.people[-1].is_victim is True
