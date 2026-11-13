import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.loaders import load_elements


def write_elements(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_elements_reads_dynamic_catalog(tmp_path: Path) -> None:
    path = write_elements(
        tmp_path / "elements.json",
        {
            "elements": [
                {"name": "rock"},
                {"name": "carpet", "is_occupiable": True},
            ]
        },
    )

    elements = load_elements(path)
    rock = elements.get("rock")
    carpet = elements.get("carpet")

    assert rock is not None
    assert rock.is_occupiable is False
    assert carpet is not None
    assert carpet.is_occupiable is True


def test_load_elements_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_elements(tmp_path / "missing.json")


def test_load_elements_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "elements.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        load_elements(path)

    assert error.value.errors()[0]["type"] == "json_invalid"
