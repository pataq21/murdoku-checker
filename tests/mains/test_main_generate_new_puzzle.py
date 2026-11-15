import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.domain import (
    AnyOfRule,
    CoordinateAxis,
    InCoordinateRule,
    Map,
    Rules,
    Solution,
)
from murdoku_checker.mains.main_generate_new_puzzle import main


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17}',
        encoding="utf-8",
    )
    return path


def test_main_generates_solution_and_its_complete_pool(
    config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(config_path)]) == 0
    captured = capsys.readouterr()
    assert "Phase timings:\n" in captured.err
    data = json.loads(captured.out)

    solution_data = data["solution"]
    solution = Solution(
        map=Map.model_validate(solution_data["map"]),
        placements={
            name: tuple(position)
            for name, position in solution_data["placements"].items()
        },
    )
    pool = Rules.model_validate({"rules": data["pool"]}).rules
    assert data["config"]["seed"] == 17
    assert solution_data["victim"] in solution.placements
    assert pool
    assert all(rule.evaluate(solution) for rule in pool)
    assert list(pool) == generate_pool(solution)


@pytest.mark.parametrize("output_format", ["json", "html"])
def test_main_logs_rule_totals_per_person_and_type(
    config_path: Path, capsys: pytest.CaptureFixture[str], output_format: str
) -> None:
    row = InCoordinateRule(person="person_1", axis=CoordinateAxis.ROW, value=0)
    column = InCoordinateRule(person="person_1", axis=CoordinateAxis.COLUMN, value=0)
    pool = {
        "person_2": [],
        "person_1": [row, column, AnyOfRule(person="person_1", conditions=(row, column))],
    }
    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_pool",
        return_value=pool,
    ):
        assert main(
            [
                str(config_path),
                "--format", output_format,
                "--output", str(config_path.parent / "solution.html"),
            ]
        ) == 0

    captured = capsys.readouterr()
    assert (
        "Generated rules per person:\n"
        "  person_1: total=3\n"
        "    any_of: 1\n"
        "    in_coordinate: 2\n"
        "  person_2: total=0\n"
        "Phase timings:\n"
    ) in captured.err
    assert "Generated rules per person:" not in captured.out


def test_main_excludes_the_generated_victim_from_the_pool(
    config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_pool",
        wraps=generate_pool,
    ) as build_pool:
        assert main([str(config_path)]) == 0

    solution = build_pool.call_args.args[0]
    victim = build_pool.call_args.kwargs["victim"]
    assert victim in solution.placements
    captured = capsys.readouterr()
    assert f"  {victim}: total=" not in captured.err
    assert all(
        f"  {person}: total=" in captured.err
        for person in solution.placements if person != victim
    )


@pytest.mark.parametrize("failure", ["missing", "infeasible", "solver", "pool"])
def test_main_reports_errors_without_partial_output(
    config_path: Path, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    if failure == "missing":
        code = main([str(config_path.parent / "missing.json")])
    else:
        target = (
            "murdoku_checker.mains.main_generate_new_puzzle.generate_pool"
            if failure == "pool"
            else "murdoku_checker.mains.main_generate_new_puzzle.generate_solution"
        )
        error = (
            ValueError("invalid solution")
            if failure == "pool"
            else RuntimeError("solver failed") if failure == "solver" else None
        )
        with patch(target, return_value=None, side_effect=error):
            code = main([str(config_path)])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "Generated rules per person:" not in captured.err
    assert {
        "missing": "Error loading generation config",
        "infeasible": "No solution for the generated specification",
        "solver": "Error generating solution",
        "pool": "Error generating clue pool",
    }[failure] in captured.err


def test_solver_logs_do_not_corrupt_output(
    config_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    assert main([str(config_path), "--solver-logs"]) == 0
    captured = capfd.readouterr()
    assert json.loads(captured.out)["pool"]
    assert "Starting CP-SAT" in captured.err


def test_module_entry_point(config_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "murdoku_checker.mains.main_generate_new_puzzle",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Phase timings:\n" in result.stderr
    assert json.loads(result.stdout)["pool"]
