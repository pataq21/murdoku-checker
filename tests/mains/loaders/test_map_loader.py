import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from murdoku_checker.mains.loaders import load_map


def write_map(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_map_reads_and_validates_json(tmp_path: Path) -> None:
    path = write_map(
        tmp_path / "map.json",
        {
            "cells": [
                {
                    "latitude": 0,
                    "longitude": 1,
                    "room": "comedor",
                    "features": ["plant"],
                },
                {"latitude": 2, "longitude": 3, "room": "cocina"},
            ]
        },
    )

    map_ = load_map(path)

    assert map_.get_cell(0, 1).features == ("plant",)  # type: ignore[union-attr]
    assert map_.get_cell(2, 3).features == ()  # type: ignore[union-attr]


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
        {"cells": [{"latitude": "0", "longitude": 1, "room": "comedor"}]},
    )

    with pytest.raises(ValidationError) as error:
        load_map(path)

    assert error.value.errors()[0]["loc"] == ("cells", 0, "latitude")


def test_load_map_rejects_duplicate_coordinates(tmp_path: Path) -> None:
    path = write_map(
        tmp_path / "map.json",
        {
            "cells": [
                {"latitude": 0, "longitude": 1, "room": "comedor"},
                {"latitude": 0, "longitude": 1, "room": "comedor"},
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
    project_root = Path(__file__).parents[3]

    map_ = load_map(
        project_root / "inputs" / "so_easy" / "example1" / "map.json"
    )

    assert len(map_.cells) == 36
    assert Counter(cell.room for cell in map_.cells) == {
        "comedor": 12,
        "dormitorio": 6,
        "cocina": 6,
        "porche": 4,
        "jardin_delantero": 8,
    }
    assert map_.get_cell(0, 1).features == ("chair",)  # type: ignore[union-attr]
    assert map_.get_cell(1, 4).features == ("plant",)  # type: ignore[union-attr]
    assert map_.get_cell(5, 4).features == ("tree",)  # type: ignore[union-attr]
