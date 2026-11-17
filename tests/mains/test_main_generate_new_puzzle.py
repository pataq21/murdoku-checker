import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.domain import (
    AnyOfRule,
    CoordinateAxis,
    GenerationConfig,
    InCoordinateRule,
    Map,
    MurdokuInput,
    Rule,
    Rules,
    Solution,
)
from murdoku_checker.mains.main_generate_new_puzzle import main
from murdoku_checker.apps.solution_checker import check_solutions


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17, '
        '"target_difficulty": 4}',
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("rule_types", [["in_coordinate"]])
def test_main_uses_rule_types_from_the_input(
    config_path: Path, capsys: pytest.CaptureFixture[str], rule_types: list[str]
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["rule_types"] = rule_types
    config_path.write_text(json.dumps(config), encoding="utf-8")
    parsed = GenerationConfig.model_validate_json(config_path.read_bytes())
    assert json.loads(parsed.model_dump_json())["rule_types"] == rule_types

    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_pool",
        wraps=generate_pool,
    ) as build_pool:
        assert main([str(config_path)]) == 0

    assert build_pool.call_args.kwargs["rule_types"] == tuple(rule_types)
    solution = build_pool.call_args.args[0]
    victim = build_pool.call_args.kwargs["victim"]
    expected = generate_pool(solution, victim=victim, rule_types=parsed.rule_types)
    assert all(rule.type in rule_types for rules in expected.values() for rule in rules)
    captured = capsys.readouterr()
    assert f"total={len(next(iter(expected.values())))}" in captured.err
    assert "any_of:" not in captured.err
    data = json.loads(captured.out)
    assert data["config"]["rule_types"] == rule_types
    assert Rules.model_validate({"rules": data["pool"]}).rules == tuple(
        rule for rules in expected.values() for rule in rules
    )


@pytest.mark.parametrize("rule_types", [["unknown"], "in", None, [1]])
def test_main_rejects_invalid_rule_types_before_generation(
    config_path: Path, capsys: pytest.CaptureFixture[str], rule_types: object
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["rule_types"] = rule_types
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_specification"
    ) as generate:
        assert main([str(config_path)]) == 1
    generate.assert_not_called()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error loading generation config" in captured.err
    assert "rule_types" in captured.err


@pytest.mark.parametrize("custom_names", [False, True])
def test_main_generates_solution_and_its_complete_pool(
    config_path: Path, capsys: pytest.CaptureFixture[str], custom_names: bool,
) -> None:
    if custom_names:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["person_names"] = ["Alice", "Bob"]
        config_path.write_text(json.dumps(config), encoding="utf-8")
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
    if custom_names:
        assert set(solution.placements) == {"Alice", "Bob"}
        assert solution_data["victim"] == "Bob"
    assert pool
    assert all(rule.evaluate(solution) for rule in pool)
    assert all(rule.person != solution_data["victim"] for rule in pool)
    expected_pool = generate_pool(solution, victim=solution_data["victim"])
    assert list(pool) == [
        rule for rules in expected_pool.values() for rule in rules
    ]
    puzzle = MurdokuInput.model_validate_json(json.dumps(data["puzzle"]))
    checked = check_solutions(puzzle)
    assert checked.count == 1
    assert checked.first_solution == solution.placements
    assert data["optimization"]["difficulty_error"] == 0
    assert data["optimization"]["rule_count"] == 2


@pytest.mark.parametrize("output_format", ["json", "html"])
def test_main_logs_rule_totals_per_person_and_type(
    config_path: Path, capsys: pytest.CaptureFixture[str], output_format: str
) -> None:
    pool: dict[str, list[Rule]] = {}

    def example_pool(
        solution: Solution, **kwargs: object
    ) -> dict[str, list[Rule]]:
        person = next(name for name in solution.placements if name != kwargs["victim"])
        row_value, column_value = solution.position_of(person)
        row = InCoordinateRule(
            person=person, axis=CoordinateAxis.ROW, value=row_value
        )
        column = InCoordinateRule(
            person=person, axis=CoordinateAxis.COLUMN, value=column_value
        )
        pool.update({
            "person_2": [],
            person: [row, column, AnyOfRule(person=person, conditions=(row, column))],
        })
        return pool

    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_pool",
        side_effect=example_pool,
    ):
        assert (
            main(
                [
                    str(config_path),
                    "--format",
                    output_format,
                    "--output",
                    str(config_path.parent / "solution.html"),
                ]
            )
            == 0
        )

    captured = capsys.readouterr()
    assert (
        "Generated rules per person:\n"
        "  person_1: total=3\n"
        "    any_of: 1\n"
        "    in_coordinate: 2\n"
        "  person_2: total=0\n"
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
        for person in solution.placements
        if person != victim
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
            else RuntimeError("solver failed")
            if failure == "solver"
            else None
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


@pytest.mark.parametrize("target_difficulty", [0, 4, 100])
def test_progress_reports_completed_candidates_and_real_target_error(
    config_path: Path, capsys: pytest.CaptureFixture[str], target_difficulty: int
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(
        target_difficulty=target_difficulty,
        rule_types=["in_coordinate"],
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert main([str(config_path)]) == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    optimization = data["optimization"]
    lines = [
        line for line in captured.err.splitlines() if line.startswith("Candidate ")
    ]
    assert len(lines) == optimization["iterations"]
    for index, line in enumerate(lines, start=1):
        match = re.fullmatch(
            r"Candidate (\d+) checked: difficulty=(\d+) target=(\d+) "
            r"error=(\d+) clues=(\d+) status=(unique|ambiguous)",
            line,
        )
        assert match is not None
        iteration, difficulty, target, error, _ = map(int, match.groups()[:5])
        assert iteration == index
        assert target == target_difficulty
        assert error == abs(difficulty - target)
        assert match.group(6) == ("unique" if index == len(lines) else "ambiguous")
    assert (
        f"Puzzle summary: candidates_checked={optimization['iterations']} "
        f"cuts={optimization['iterations'] - 1} unique_puzzles=1 "
        f"difficulty={optimization['total_difficulty']} target={target_difficulty} "
        f"error={optimization['difficulty_error']} clues={optimization['rule_count']}"
    ) in captured.err
    assert "Starting CP-SAT" not in captured.err
    directory, = (config_path.parent / "use_cases" / "generate-puzzle" / "outputs").iterdir()
    assert (directory / "run.log").read_text(encoding="utf-8") == captured.err


def test_module_entry_point(config_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "murdoku_checker.mains.main_generate_new_puzzle",
            str(config_path),
            "--runs-dir",
            str(config_path.parent / "runs"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Phase timings:\n" in result.stderr
    assert json.loads(result.stdout)["pool"]


@pytest.mark.parametrize("target", ["missing", None, -1, True, 2.5])
def test_target_is_required_and_must_be_a_nonnegative_integer(
    config_path: Path, capsys: pytest.CaptureFixture[str], target: object
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if target == "missing":
        del config["target_difficulty"]
    else:
        config["target_difficulty"] = target
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_specification"
    ) as generate:
        assert main([str(config_path)]) == 1
    generate.assert_not_called()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "target_difficulty" in captured.err


def test_empty_pool_reports_failure_without_saving_a_puzzle(
    config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["rule_types"] = []
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert main([str(config_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error building puzzle" in captured.err
    assert "Puzzle summary:" not in captured.err
    directory, = (config_path.parent / "use_cases" / "generate-puzzle" / "outputs").iterdir()
    assert not (directory / "result.json").exists()
