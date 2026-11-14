import json
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.domain import MurdokuInput
from murdoku_checker.mains.main_verify_puzzle import (
    load_input_elements,
    load_input_map,
    load_input_people,
    load_input_rules,
    main,
)
from murdoku_checker.apps.solution_checker import SolveResult


def write_map(input_directory: Path, data: object) -> Path:
    input_directory.mkdir()
    map_path = input_directory / "map.json"
    map_path.write_text(json.dumps(data), encoding="utf-8")
    feature_names = sorted(
        {
            feature
            for cell in data.get("cells", [])  # type: ignore[union-attr]
            for feature in cell.get("features", [])
        }
    )
    (input_directory / "elements.json").write_text(
        json.dumps(
            {"elements": [{"name": feature} for feature in feature_names]}
        ),
        encoding="utf-8",
    )
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

    assert map_.get_cell(2, 3).features == ("counter",)  # type: ignore[union-attr]


def test_load_input_elements_reads_elements_json_from_case_directory(
    tmp_path: Path,
) -> None:
    input_directory = tmp_path / "case"
    write_map(input_directory, {"cells": []})
    (input_directory / "elements.json").write_text(
        '{"elements":[{"name":"chair","is_occupiable":true}]}',
        encoding="utf-8",
    )

    elements = load_input_elements(input_directory)
    chair = elements.get("chair")

    assert chair is not None
    assert chair.is_occupiable is True


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
    assert captured.out.startswith(
        f"Loaded map from '{input_directory / 'map.json'}' with 2 cells.\n"
        f"Loaded elements from '{input_directory / 'elements.json'}' "
        "with 0 elements.\n"
        f"Loaded people from '{input_directory / 'people.json'}' with 2 people.\n"
        f"Loaded rules from '{input_directory / 'rules.json'}' with 1 rules.\n"
        "Multiple solutions (at least 2). Showing the first.\n"
    )
    assert captured.out.count("First solution (") == 1
    assert "P1 = Alice" in captured.out
    assert "P2 = Bob" in captured.out
    assert captured.err == ""


def test_main_prints_unique_solution_without_solver_logs(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
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

    exit_code = main([str(input_directory)])
    captured = capfd.readouterr()

    assert exit_code == 0
    assert "Unique solution.\nFirst solution (" in captured.out
    assert "0 | P1/R1 |" in captured.out
    assert "P1 = Alice (latitude=0, longitude=0)" in captured.out
    assert "R1 = comedor" in captured.out
    assert "Starting CP-SAT" not in captured.out
    assert "CpSolverResponse" not in captured.out
    assert captured.err == ""


def test_main_delegates_to_solution_checker(tmp_path: Path) -> None:
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

    with patch(
        "murdoku_checker.mains.main_verify_puzzle.check_solutions",
        return_value=SolveResult(0, None),
    ) as check_solutions:
        exit_code = main([str(input_directory)])

    assert exit_code == 0
    check_solutions.assert_called_once()
    assert isinstance(check_solutions.call_args.args[0], MurdokuInput)


@pytest.mark.parametrize("has_person", [False, True])
def test_main_handles_empty_map(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], has_person: bool
) -> None:
    input_directory = tmp_path / "case"
    write_map(input_directory, {"cells": []})
    write_people(
        input_directory,
        {"people": [{"name": "Alice", "gender": "Female"}] if has_person else []},
    )
    write_rules(input_directory, {"rules": []})

    assert main([str(input_directory)]) == 0
    captured = capsys.readouterr()

    if has_person:
        assert captured.out.endswith("No solution.\n")
        assert "First solution" not in captured.out
    else:
        assert captured.out.endswith("Unique solution.\nFirst solution: empty map.\n")
    assert captured.err == ""


def test_main_reports_solver_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_directory = tmp_path / "case"
    write_map(input_directory, {"cells": []})
    write_people(input_directory, {"people": []})
    write_rules(input_directory, {"rules": []})

    with patch(
        "murdoku_checker.mains.main_verify_puzzle.check_solutions",
        side_effect=RuntimeError("inconclusive result"),
    ):
        assert main([str(input_directory)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert (
        f"Error solving input '{input_directory}': inconclusive result" in captured.err
    )


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


def test_main_reports_missing_elements(
    tmp_path: Path,
    capsys: object,
) -> None:
    input_directory = tmp_path / "missing-elements"
    write_map(input_directory, {"cells": []})
    (input_directory / "elements.json").unlink()

    exit_code = main([str(input_directory)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert exit_code == 1
    assert captured.out == ""
    assert f"Error loading input '{input_directory}'" in captured.err
    assert "elements.json" in captured.err
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
