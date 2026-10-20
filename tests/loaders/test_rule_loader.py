import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.domain import AnyOf, In, NextTo
from murdoku_checker.loaders import load_rules


def write_rules(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_rules_reads_and_validates_json(tmp_path: Path) -> None:
    path = write_rules(
        tmp_path / "rules.json",
        {
            "rules": [
                {
                    "person": "Alex",
                    "condition": {
                        "type": "next_to",
                        "element": {"type": "feature", "value": "plant"},
                    },
                }
            ]
        },
    )

    rules = load_rules(path)

    assert len(rules.rules) == 1
    assert isinstance(rules.rules[0].condition, NextTo)


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
    project_root = Path(__file__).parents[2]

    rules = load_rules(project_root / "inputs" / "example" / "rules.json")

    assert len(rules.rules) == 5
    assert isinstance(rules.rules[0].condition, NextTo)
    assert isinstance(rules.rules[1].condition, In)
    assert isinstance(rules.rules[-1].condition, AnyOf)
