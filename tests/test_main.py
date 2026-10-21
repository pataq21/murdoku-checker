import json
from pathlib import Path
from unittest.mock import patch

from murdoku_checker.domain import CellFeature, MurdokuInput
from murdoku_checker.main import (
    load_input_map,
    load_input_people,
    load_input_rules,
    main,
)


def write_map(input_directory: Path, data: object) -> Path:
    input_directory.mkdir()
    map_path = input_directory / "map.json"
    map_path.write_text(json.dumps(data), encoding="utf-8")
    return map_path


def write_people(input_directory: Path, data: object) -> Path:
    people_path = input_directory / "people.json"
    people_path.write_text(json.dumps(data), encoding="utf-8")
    return people_path


def write_rules(input_directory: Path, data: object) -> Path:
    rules_path = input_directory / "rules.json"
    rules_path.write_text(json.dumps(data), encoding="utf-8")
    return rules_path


def test_load_input_map_reads_map_json_from_case_directory(tmp_path: Path) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {
            "cells": [
                {
                    "latitude": 2,
                    "longitude": 3,
                    "room": "cocina",
                    "features": ["counter"],
                }
            ]
        },
    )

    map_ = load_input_map(input_directory)

    assert map_.get_cell(2, 3).features == (CellFeature.COUNTER,)  # type: ignore[union-attr]


def test_load_input_people_reads_people_json_from_case_directory(
    tmp_path: Path,
) -> None:
    input_directory = tmp_path / "case"
    input_directory.mkdir()
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Female"}]},
    )

    people = load_input_people(input_directory)

    assert people.people[0].name == "Alice"


def test_load_input_rules_reads_rules_json_from_case_directory(
    tmp_path: Path,
) -> None:
    input_directory = tmp_path / "case"
    input_directory.mkdir()
    write_rules(input_directory, {"rules": []})

    rules = load_input_rules(input_directory)

    assert rules.rules == ()


def test_main_loads_map_and_prints_summary(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {
            "cells": [
                {"latitude": 0, "longitude": 0, "room": "comedor"},
                {"latitude": 1, "longitude": 1, "room": "comedor"},
            ]
        },
    )
    write_people(
        input_directory,
        {
            "people": [
                {"name": "Alice", "gender": "Female"},
                {"name": "Bob", "gender": "Male"},
            ]
        },
    )
    write_rules(
        input_directory,
        {
            "rules": [
                {
                    "person": "Alice",
                    "condition": {
                        "type": "in",
                        "element": {"type": "room", "value": "comedor"},
                    },
                }
            ]
        },
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 0
    assert captured.out == (
        f"Loaded map from '{input_directory / 'map.json'}' with 2 cells.\n"
        f"Loaded people from '{input_directory / 'people.json'}' with 2 people.\n"
        f"Loaded rules from '{input_directory / 'rules.json'}' with 1 rules.\n"
        "2\n"
    )
    assert captured.err == ""


def test_main_prints_solution_count(tmp_path: Path, capsys: object) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {"cells": [{"latitude": 0, "longitude": 0, "room": "comedor"}]},
    )
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Female"}]},
    )
    write_rules(input_directory, {"rules": []})

    with patch("murdoku_checker.main.ModelBuilder") as builder_type:
        builder_type.return_value.build.return_value.solve.return_value = 7
        exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 0
    assert captured.out.splitlines()[-1] == "7"


def test_main_builds_optimization_model(tmp_path: Path) -> None:
    input_directory = tmp_path / "case"
    write_map(
        input_directory,
        {"cells": [{"latitude": 0, "longitude": 0, "room": "comedor"}]},
    )
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Female"}]},
    )
    write_rules(input_directory, {"rules": []})

    with patch("murdoku_checker.main.ModelBuilder") as builder_type:
        exit_code = main([str(input_directory)])

    assert exit_code == 0
    builder_type.return_value.build.assert_called_once()
    input_ = builder_type.return_value.build.call_args.args[0]
    assert isinstance(input_, MurdokuInput)


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
        {"cells": [{"latitude": "0", "longitude": 0, "room": "comedor"}]},
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "validation error" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_missing_people(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "missing-people"
    write_map(input_directory, {"cells": []})

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "people.json" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_invalid_people(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "invalid-people"
    write_map(input_directory, {"cells": []})
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Unknown"}]},
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "validation error" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_missing_rules(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "missing-rules"
    write_map(input_directory, {"cells": []})
    write_people(input_directory, {"people": []})

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "rules.json" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_invalid_rules(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "invalid-rules"
    write_map(input_directory, {"cells": []})
    write_people(input_directory, {"people": []})
    write_rules(
        input_directory,
        {"rules": [{"person": "Alice", "condition": {"type": "unknown"}}]},
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "validation error" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_invalid_rule_reference(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "invalid-rule-reference"
    write_map(
        input_directory,
        {"cells": [{"latitude": 0, "longitude": 0, "room": "comedor"}]},
    )
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Female"}]},
    )
    write_rules(
        input_directory,
        {
            "rules": [
                {
                    "person": "Alice",
                    "condition": {
                        "type": "next_to",
                        "element": {"type": "feature", "value": "plant"},
                    },
                }
            ]
        },
    )

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert "unknown feature in rule: plant" in captured.err
    assert "Traceback" not in captured.err
