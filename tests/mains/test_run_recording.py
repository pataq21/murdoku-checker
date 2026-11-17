import json
import shutil
from collections.abc import Callable, Sequence
from html import escape
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.domain import Rules
from murdoku_checker.mains.main_generate_new_puzzle import main as generate_puzzle
from murdoku_checker.mains.main_generate_solution import main as generate_solution
from murdoku_checker.mains.main_verify_puzzle import main as verify_puzzle
from murdoku_checker.mains.run_recording import RunRecord


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "input.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17, '
        '"rule_types": ["in_coordinate"], "target_difficulty": 4}',
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("command", "use_case"),
    [(generate_puzzle, "generate-puzzle"), (generate_solution, "generate-solution")],
)
@pytest.mark.parametrize("output_format", ["json", "text", "html"])
def test_generation_records_context_and_artifacts_for_every_format(
    tmp_path: Path,
    config_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: Callable[[Sequence[str] | None], int],
    use_case: str,
    output_format: str,
) -> None:
    original = config_path.read_bytes()
    arguments = [str(config_path), "--format", output_format, "--solver-logs"]
    output_copy = tmp_path / "copy.html"
    if output_format == "html":
        arguments.extend(["--output", str(output_copy)])
    assert command(arguments) == 0
    captured = capsys.readouterr()
    directory, = (tmp_path / "use_cases" / use_case / "outputs").iterdir()
    metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))

    assert f"Run directory: {directory}" in captured.err
    assert (directory / "input.json").read_bytes() == original
    assert metadata["status"] == "succeeded"
    assert metadata["exit_code"] == 0
    assert metadata["use_case"] == use_case
    assert metadata["effective_config"]["seed"] == 17
    assert metadata["effective_config"]["rule_types"] == ["in_coordinate"]
    assert metadata["inputs"]["input.json"] == str(config_path.resolve())
    assert metadata["arguments"][0] == str(config_path)
    assert metadata["started_at"] <= metadata["finished_at"]
    assert metadata["total_seconds"] >= sum(metadata["timings"].values())
    assert metadata["code"]["revision"]
    assert metadata["code"]["packages"]["ortools"]
    assert "generate_solution" in metadata["timings"]
    filename = "puzzle.html" if use_case == "generate-puzzle" else "solution.html"
    html = (directory / filename).read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert {path.name for path in directory.glob("*.html")} == {filename}
    if output_format == "html":
        assert output_copy.read_text(encoding="utf-8") == html
    log = (directory / "run.log").read_text(encoding="utf-8")
    assert log == captured.err
    assert "Starting CP-SAT" in log
    assert "Phase timings:" in log
    if output_format == "json":
        assert result == json.loads(captured.out)
    if use_case == "generate-puzzle":
        assert result["pool"]
        assert result["puzzle"]["rules"]["rules"]
        assert result["optimization"]["difficulty_error"] == 0
        assert "build_problem" in metadata["timings"]
        assert all(
            rule["condition"]["type"] == "in_coordinate" for rule in result["pool"]
        )
        rules = Rules.model_validate(result["puzzle"]["rules"])
        assert "Selected clues" in html
        assert all(
            f"<li>{escape(rule.description)}</li>" in html for rule in rules.rules
        )
        assert "<title>Murdoku - Generated puzzle</title>" in html
        assert 'id="solution-toggle"' in html
        assert '<div class="person' in html
        assert "<small data-solution hidden>Row " in html
        if output_format == "html":
            assert captured.out.count("HTML puzzle written to") == 1
            assert "HTML solution written" not in captured.out
    else:
        assert "Selected clues" in html
        assert (
            f"<li>{escape(result['victim'])} is the victim. "
            "It was alone with someone</li>"
        ) in html
        assert not (directory / "puzzle.html").exists()

    config_path.write_text("changed after the run", encoding="utf-8")
    assert (directory / "input.json").read_bytes() == original


def test_unseeded_run_can_be_replayed_without_overwriting_previous_runs(
    tmp_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    del config["seed"]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    runs = tmp_path / "recorded"

    assert generate_puzzle([str(config_path), "--runs-dir", str(runs)]) == 0
    first = capsys.readouterr()
    directory, = runs.iterdir()
    saved_config = directory / "config.json"
    effective = json.loads(saved_config.read_text(encoding="utf-8"))
    assert isinstance(effective["seed"], int)
    assert "seed" not in json.loads((directory / "input.json").read_text(encoding="utf-8"))

    assert generate_puzzle([str(saved_config), "--runs-dir", str(runs)]) == 0
    second = capsys.readouterr()
    assert json.loads(second.out) == json.loads(first.out)
    assert len(list(runs.iterdir())) == 2
    assert (directory / "input.json").read_text(encoding="utf-8") == json.dumps(config)


@pytest.mark.parametrize("failure", ["invalid", "missing", "infeasible", "solver"])
def test_failed_generation_keeps_context_and_diagnostics(
    tmp_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    if failure == "invalid":
        config_path.write_bytes(b"{invalid")
    elif failure == "missing":
        config_path.unlink()
    with patch(
        "murdoku_checker.mains.main_generate_new_puzzle.generate_solution",
        return_value=None,
        side_effect=RuntimeError("solver failed") if failure == "solver" else None,
    ):
        assert generate_puzzle([str(config_path)]) == 1
    captured = capsys.readouterr()
    directory, = (tmp_path / "use_cases" / "generate-puzzle" / "outputs").iterdir()
    metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert captured.out == ""
    assert metadata["status"] == "failed"
    assert metadata["exit_code"] == 1
    assert "load_config" in metadata["timings"]
    assert (directory / "run.log").read_text(encoding="utf-8") == captured.err
    assert not (directory / "result.json").exists()
    if failure != "missing":
        assert (directory / "input.json").read_bytes() == config_path.read_bytes()


@pytest.mark.parametrize("valid", [False, True])
def test_verification_snapshots_complete_input_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], valid: bool
) -> None:
    example = (
        Path(__file__).parents[2] / "use_cases" / "verify-puzzle" / "inputs"
        / "so_easy" / "example1"
    )
    source = tmp_path / "case"
    shutil.copytree(example, source)
    if not valid:
        (source / "map.json").write_text("{invalid", encoding="utf-8")
    assert verify_puzzle([str(source)]) == (0 if valid else 1)
    captured = capsys.readouterr()
    directory, = (tmp_path / "use_cases" / "verify-puzzle" / "outputs").iterdir()
    for path in source.iterdir():
        assert (directory / "inputs" / path.name).read_bytes() == path.read_bytes()
    metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert metadata["status"] == ("succeeded" if valid else "failed")
    assert (directory / "run.log").read_text(encoding="utf-8") == captured.err
    if valid:
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        assert result["count"] == 1
        assert result["first_solution"]
        assert (directory / "solution.txt").read_text(encoding="utf-8") == captured.out
        assert "Unique solution." in (directory / "solution.html").read_text(
            encoding="utf-8"
        )
    else:
        assert not (directory / "result.json").exists()


def test_archive_write_failure_is_not_reported_as_success(
    tmp_path: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_json = RunRecord.write_json

    def fail_result(record: RunRecord, name: str, data: object) -> None:
        if name == "result.json":
            raise PermissionError("archive is read-only")
        write_json(record, name, data)

    with patch.object(RunRecord, "write_json", fail_result):
        assert generate_solution([str(config_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error recording run" in captured.err
    directory, = (tmp_path / "use_cases" / "generate-solution" / "outputs").iterdir()
    metadata = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["exit_code"] == 1
    assert metadata["error"] == "archive is read-only"
