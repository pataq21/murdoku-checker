import json
from pathlib import Path
from unittest.mock import patch

import pytest

from murdoku_checker.mains.main_generate_solution import main


def test_main_prints_repeatable_solution_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = {
        "rows": 3,
        "columns": 3,
        "element_coverage_percent": 50,
        "element_type_count": 3,
        "room_count": 3,
        "seed": 17,
    }
    path = tmp_path / "generation.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    assert main([str(path)]) == 0
    first = capsys.readouterr()
    data = json.loads(first.out)

    assert first.err.startswith("Phase timings:\n")
    assert "  generate_solution:" in first.err
    assert "  output:" in first.err
    assert data["config"] == config
    assert data["person_count"] == 3
    assert data["element_cell_count"] == 4
    assert len(data["elements"]) == 3
    assert len({item["element"]["name"] for item in data["elements"]}) == 3
    assert sum(item["size"] * item["count"] for item in data["elements"]) == 4
    for item in data["elements"]:
        assert isinstance(item["element"]["is_occupiable"], bool)
        assert item["size"] in (1, 2)
        assert item["count"] >= 1
    cells = data["map"]["cells"]
    assert len(cells) == 9
    assert len({cell["room"] for cell in cells}) == 3
    assert len(data["placements"]) == 3
    assert len({position[0] for position in data["placements"].values()}) == 3
    assert len({position[1] for position in data["placements"].values()}) == 3
    assert sum(len(item["cells"]) for item in data["furniture"]) == 4
    assert data["victim"] == "person_3"
    rooms_by_position = {
        (cell["latitude"], cell["longitude"]): cell["room"] for cell in cells
    }
    victim_room = rooms_by_position[tuple(data["placements"][data["victim"]])]
    assert sum(
        rooms_by_position[tuple(position)] == victim_room
        for position in data["placements"].values()
    ) == 2

    assert main([str(path)]) == 0
    second = capsys.readouterr()
    assert second.out == first.out
    assert second.err.startswith("Phase timings:\n")


def test_main_displays_generated_grid_in_text_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17}',
        encoding="utf-8",
    )

    assert main([str(path), "--format", "text"]) == 0
    captured = capsys.readouterr()

    assert captured.err.startswith("Phase timings:\n")
    assert captured.out.startswith("Generated solution (rows = latitude")
    assert "P1/R1" in captured.out
    assert "P2*/R1" in captured.out
    assert "P2* = person_2 (victim)" in captured.out
    assert "R1 = room_1" in captured.out


def test_main_solver_logs_do_not_corrupt_json_output(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17}',
        encoding="utf-8",
    )

    assert main([str(path), "--solver-logs"]) == 0
    captured = capfd.readouterr()

    data = json.loads(captured.out)
    assert set(data["placements"]) == {"person_1", "person_2"}
    assert data["victim"] == "person_2"
    assert "Starting CP-SAT" in captured.err
    assert "CpSolverResponse" in captured.err


@pytest.mark.parametrize("writable", [True, False])
def test_main_writes_html_or_reports_output_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], writable: bool
) -> None:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 2, "columns": 2, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1, "seed": 17}',
        encoding="utf-8",
    )
    output = tmp_path / "solution.html" if writable else tmp_path / "missing" / "solution.html"

    code = main([str(path), "--format", "html", "--output", str(output)])
    captured = capsys.readouterr()

    if writable:
        assert code == 0
        assert captured.err.startswith("Phase timings:\n")
        assert "HTML solution written to" in captured.out
        content = output.read_text(encoding="utf-8")
        assert content.startswith("<!doctype html>")
        assert "person_1" in content
        assert "room_1" in content
        assert "person_2 (victim)" in content
    else:
        assert code == 1
        assert captured.out == ""
        assert "Error writing HTML solution" in captured.err
        assert not output.exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--format", "html"],
        ["--format", "text", "--output", "solution.html"],
        ["--output", "solution.html"],
    ],
)
def test_main_rejects_incompatible_output_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["unused.json", *arguments])

    assert error.value.code == 2


def test_main_does_not_overwrite_input_with_html(tmp_path: Path) -> None:
    path = tmp_path / "generation.json"
    path.write_text("keep this input", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        main([str(path), "--format", "html", "--output", str(path)])

    assert error.value.code == 2
    assert path.read_text(encoding="utf-8") == "keep this input"


@pytest.mark.parametrize(
    "content",
    [
        None,
        b"{",
        b'{"rows": "\xff"}',
        b'{"rows": 3, "columns": 3, "element_coverage_percent": 5, '
        b'"element_type_count": 3, "room_count": 3}',
    ],
    ids=["missing-file", "invalid-json", "invalid-utf8", "incompatible-config"],
)
def test_main_reports_input_errors_without_partial_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: bytes | None
) -> None:
    path = tmp_path / "generation.json"
    if content is not None:
        path.write_bytes(content)

    assert main([str(path)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert f"Error loading generation config '{path}'" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("solver_error", [False, True])
def test_main_reports_unsuccessful_generation_without_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], solver_error: bool
) -> None:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 1, "columns": 1, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1}',
        encoding="utf-8",
    )
    with patch(
        "murdoku_checker.mains.main_generate_solution.generate_solution",
        return_value=None,
        side_effect=RuntimeError("inconclusive result") if solver_error else None,
    ) as generate:
        assert main([str(path)]) == 1

    generate.assert_called_once()
    captured = capsys.readouterr()
    assert captured.out == ""
    if solver_error:
        assert "Error generating solution: inconclusive result" in captured.err
    else:
        assert "No solution for the generated specification" in captured.err
    assert "Traceback" not in captured.err


def test_main_reports_single_person_board_as_infeasible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "generation.json"
    path.write_text(
        '{"rows": 1, "columns": 1, "element_coverage_percent": 0, '
        '"element_type_count": 0, "room_count": 1}',
        encoding="utf-8",
    )

    assert main([str(path)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "No solution for the generated specification" in captured.err
