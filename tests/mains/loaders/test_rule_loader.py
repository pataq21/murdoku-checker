import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import (
    AnyOfRule,
    Direction,
    InRule,
    NextToRule,
    NotNextToRule,
    PersonElement,
    RelativePositionRule,
)
from murdoku_checker.mains.loaders import load_rules


def write_rules(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("condition_type", "expected"),
    [("next_to", NextToRule), ("not_next_to", NotNextToRule)],
)
def test_load_rules_reads_and_validates_json(
    tmp_path: Path,
    condition_type: str,
    expected: type[NextToRule] | type[NotNextToRule],
) -> None:
    path = write_rules(
        tmp_path / "rules.json",
        {
            "rules": [
                {
                    "person": "Alex",
                    "condition": {
                        "type": condition_type,
                        "element": {"type": "feature", "value": "plant"},
                    },
                }
            ]
        },
    )

    rules = load_rules(path)

    assert len(rules.rules) == 1
    assert isinstance(rules.rules[0], expected)
    assert rules.rules[0].person == "Alex"


def test_load_rules_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_rules(tmp_path / "missing.json")


def test_load_rules_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        load_rules(path)

    assert error.value.errors()[0]["type"] == "json_invalid"


def test_load_rules_rejects_invalid_condition(tmp_path: Path) -> None:
    path = write_rules(
        tmp_path / "rules.json",
        {"rules": [{"person": "Alex", "condition": {"type": "unknown"}}]},
    )

    with pytest.raises(ValidationError) as error:
        load_rules(path)

    assert error.value.errors()[0]["type"] == "union_tag_invalid"


def test_load_rules_rejects_unknown_fields(tmp_path: Path) -> None:
    path = write_rules(tmp_path / "rules.json", {"rules": [], "name": "invalid"})

    with pytest.raises(ValidationError) as error:
        load_rules(path)

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_load_example_rules() -> None:
    project_root = Path(__file__).parents[3]

    rules = load_rules(
        project_root / "use_cases" / "verify-puzzle" / "inputs"
        / "so_easy" / "example1" / "rules.json"
    )

    assert len(rules.rules) == 5
    assert isinstance(rules.rules[0], NextToRule)
    assert isinstance(rules.rules[1], InRule)
    assert isinstance(rules.rules[-1], AnyOfRule)
    assert {child.person for child in rules.rules[-1].conditions} == {
        rules.rules[-1].person
    }


def test_load_relative_position_rule_from_example2(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[3]
    source = (
        project_root / "use_cases" / "verify-puzzle" / "inputs"
        / "so_easy" / "example2" / "rules.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    rule = next(rule for rule in data["rules"] if rule["person"] == "Brigitte")
    path = write_rules(tmp_path / "rules.json", {"rules": [rule]})

    loaded = load_rules(path).rules[0]

    assert isinstance(loaded, RelativePositionRule)
    assert loaded.person == "Brigitte"
    assert loaded.direction is Direction.SOUTH
    assert loaded.element == PersonElement(value="Cameron")
