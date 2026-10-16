import json
from pathlib import Path

from murdoku_checker.main import load_input_map, main


def write_map(input_directory: Path, data: object) -> Path:
    input_directory.mkdir()
    map_path = input_directory / "map.json"
    map_path.write_text(json.dumps(data), encoding="utf-8")
    return map_path


def test_load_input_map_reads_map_json_from_case_directory(tmp_path: Path) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {"cells": [{"latitude": 2, "longitude": 3, "has_sofa": True}]},
    )

    map_ = load_input_map(input_directory)

    assert map_.get_cell(2, 3).has_sofa is True  # type: ignore[union-attr]


def test_main_loads_map_and_prints_summary(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {
            "cells": [
                {"latitude": 0, "longitude": 0},
                {"latitude": 1, "longitude": 1},
            ]
        },
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 0
    assert captured.out == (
        f"Loaded map from '{input_directory / 'map.json'}' with 2 cells.\n"
    )
    assert captured.err == ""


def test_main_reports_missing_map(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "missing"

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_invalid_map(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "invalid"
    write_map(
        input_directory,
        {"cells": [{"latitude": "0", "longitude": 0}]},
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "validation error" in captured.err
    assert "Traceback" not in captured.err
