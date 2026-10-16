import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.loaders import load_map


def write_map(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_map_reads_and_validates_json(tmp_path: Path) -> None:
    path = write_map(
        tmp_path / "map.json",
        {
            "cells": [
                {"latitude": 0, "longitude": 1, "has_plant": True},
                {"latitude": 2, "longitude": 3},
            ]
        },
    )

    map_ = load_map(path)

    assert map_.get_cell(0, 1).has_plant is True  # type: ignore[union-attr]
    assert map_.get_cell(2, 3).has_chair is False  # type: ignore[union-attr]


def test_load_map_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_map(tmp_path / "missing.json")


def test_load_map_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ValidationError) as error:
        load_map(path)

    assert error.value.errors()[0]["type"] == "json_invalid"


def test_load_map_rejects_invalid_cell(tmp_path: Path) -> None:
    path = write_map(
        tmp_path / "map.json",
        {"cells": [{"latitude": "0", "longitude": 1}]},
    )

    with pytest.raises(ValidationError) as error:
        load_map(path)

    assert error.value.errors()[0]["loc"] == ("cells", 0, "latitude")


def test_load_map_rejects_duplicate_coordinates(tmp_path: Path) -> None:
    path = write_map(
        tmp_path / "map.json",
        {
            "cells": [
                {"latitude": 0, "longitude": 1},
                {"latitude": 0, "longitude": 1},
            ]
        },
    )

    with pytest.raises(ValidationError, match="duplicate cell coordinates"):
        load_map(path)


def test_load_map_rejects_unknown_fields(tmp_path: Path) -> None:
    path = write_map(tmp_path / "map.json", {"cells": [], "name": "invalid"})

    with pytest.raises(ValidationError) as error:
        load_map(path)

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_load_example_map() -> None:
    project_root = Path(__file__).parents[2]

    map_ = load_map(project_root / "inputs" / "example" / "map.json")

    assert len(map_.cells) == 4
    assert map_.get_cell(0, 0).has_carpet is True  # type: ignore[union-attr]
    assert map_.get_cell(1, 1).has_chair is True  # type: ignore[union-attr]