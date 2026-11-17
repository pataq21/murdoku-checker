import re
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.mains.main_generate_new_puzzle import main as generate_puzzle
from murdoku_checker.mains.main_generate_solution import main as generate_solution
from murdoku_checker.mains.main_verify_puzzle import main as verify_puzzle
from murdoku_checker.mains.phase_timings import log_run_timings


@pytest.mark.parametrize("failed", [False, True])
def test_timings_measure_phases_and_report_at_the_end(
    capsys: pytest.CaptureFixture[str], failed: bool
) -> None:
    with patch(
        "murdoku_checker.mains.phase_timings.perf_counter",
        side_effect=[10.0, 11.0, 13.5, 14.0, 17.0, 18.0],
    ):
        expected_error = pytest.raises(ValueError, match="pool failed") if failed else nullcontext()
        with expected_error:
            with log_run_timings() as timings:
                with timings.phase("generate_solution"):
                    pass
                assert capsys.readouterr().err == ""
                with timings.phase("generate_pool"):
                    if failed:
                        raise ValueError("pool failed")
                assert capsys.readouterr().err == ""

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "Phase timings:\n"
        "  generate_solution: 2.500000 s\n"
        "  generate_pool: 3.000000 s\n"
        "  total: 8.000000 s\n"
    )


@pytest.mark.parametrize("command", [generate_solution, generate_puzzle, verify_puzzle])
def test_every_main_reports_only_attempted_phases_on_input_failure(
    command: Callable[[Sequence[str] | None], int],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert command([str(tmp_path / "missing")]) == 1
    captured = capsys.readouterr()
    phase = "load_map" if command is verify_puzzle else "load_config"
    assert captured.out == ""
    assert "Error loading" in captured.err
    assert re.search(
        rf"Phase timings:\n  {phase}: \d+\.\d{{6}} s\n  total: \d+\.\d{{6}} s\n$",
        captured.err,
    )
    assert "  generate_solution:" not in captured.err
    assert "  generate_pool:" not in captured.err
    assert "  check_solutions:" not in captured.err


@pytest.mark.parametrize("output_format", ["json", "text", "html"])
def test_new_puzzle_reports_executed_generation_phases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], output_format: str
) -> None:
    config = tmp_path / "generation.json"
    config.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17, '
        '"target_difficulty": 4}',
        encoding="utf-8",
    )
    output = tmp_path / "solution.html"
    assert generate_puzzle(
        [str(config), "--format", output_format, "--output", str(output)]
    ) == 0
    captured = capsys.readouterr()
    summary = captured.err.split("Phase timings:\n")[1]
    phases = ["load_config", "generate_specification", "generate_solution"]
    phases.extend(["generate_pool", "log_pool_summary", "build_problem", "output"])
    phases.append("total")
    assert [line.strip().split(":")[0] for line in summary.splitlines()] == phases
    assert all(
        re.fullmatch(r"  \w+: \d+\.\d{6} s", line) for line in summary.splitlines()
    )
    if output_format == "html":
        assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
