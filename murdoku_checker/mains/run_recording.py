import argparse
import json
import platform
import subprocess
import sys
import traceback
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr
from datetime import datetime, timezone
from importlib.metadata import version
from io import TextIOBase
from pathlib import Path
from secrets import randbelow
from typing import TextIO
from uuid import uuid4

from murdoku_checker.domain import GeneratedSolution, GenerationConfig, Rules
from murdoku_checker.mains.phase_timings import PhaseTimings, log_run_timings
from murdoku_checker.mains.solution_display_html import format_solution_html

USE_CASES_ROOT = Path("use_cases")


class _LogStream(TextIOBase):
    def __init__(self, console: TextIO, log: TextIO) -> None:
        self.console = console
        self.log = log

    def write(self, text: str) -> int:
        self.console.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self) -> None:
        self.console.flush()
        if not self.log.closed:
            self.log.flush()


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--runs-dir",
        type=Path,
        help="parent directory for run snapshots (default: use_cases/<use-case>/outputs)",
    )


def _code_context() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    context: dict[str, object] = {
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ("ortools", "pydantic")},
    }
    for key, arguments in (
        ("revision", ["rev-parse", "HEAD"]),
        ("worktree_changes", ["status", "--porcelain"]),
    ):
        try:
            result = subprocess.run(
                ["git", "--no-pager", "-C", str(root), *arguments],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            context["git_error"] = str(error)
            break
        if result.returncode:
            context["git_error"] = result.stderr.strip()
            break
        context[key] = result.stdout.strip()
    return context


class RunRecord:
    def __init__(self, directory: Path, use_case: str, arguments: Sequence[str]) -> None:
        self.directory = directory
        self.code_context = _code_context()
        self.metadata: dict[str, object] = {
            "use_case": use_case,
            "arguments": list(arguments),
            "working_directory": str(Path.cwd()),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "code": self.code_context,
            "inputs": {},
        }
        self.input_sources: dict[str, str] = {}
        self.write_json("run.json", self.metadata)

    def write_json(self, name: str, data: object) -> None:
        (self.directory / name).write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    def snapshot_input(self, source: Path, name: str) -> Path:
        self.input_sources[name] = str(source.resolve())
        self.metadata["inputs"] = self.input_sources
        target = self.directory / name
        content = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def snapshot_puzzle(self, source: Path) -> Path:
        target = self.directory / "inputs"
        target.mkdir()
        for name in ("map.json", "elements.json", "people.json", "rules.json", "image.png"):
            path = source / name
            if path.exists():
                self.snapshot_input(path, str(Path("inputs") / name))
        return target

    def load_generation_config(self, source: Path) -> GenerationConfig:
        snapshot = self.snapshot_input(source, "input.json")
        config = GenerationConfig.model_validate_json(snapshot.read_bytes())
        if config.seed is None:
            config = config.model_copy(update={"seed": randbelow(2**31)})
        self.metadata["effective_config"] = config.model_dump(mode="json")
        self.write_json("config.json", config.model_dump(mode="json"))
        self.write_json("run.json", self.metadata)
        return config

    def save_generation(
        self, generated: GeneratedSolution, result: dict[str, object],
        *, rules: Rules | None = None,
    ) -> str:
        self.write_json("result.json", result)
        is_puzzle = rules is not None
        content = format_solution_html(
            generated, rules=rules, show_solution=not is_puzzle,
        )
        name = "puzzle.html" if is_puzzle else "solution.html"
        (self.directory / name).write_text(content, encoding="utf-8")
        return content

    def finish(self, exit_code: int, timings: PhaseTimings) -> None:
        error = sys.exception()
        if error is not None:
            exit_code = 1
        self.metadata.update(
            finished_at=datetime.now(timezone.utc).isoformat(),
            exit_code=exit_code,
            status="succeeded" if exit_code == 0 and error is None else "failed",
            timings=timings.durations,
            total_seconds=timings.total_seconds,
        )
        if error is not None:
            self.metadata["error"] = str(error)
            traceback.print_exception(error, file=sys.stderr)
        self.write_json("run.json", self.metadata)


def run_recorded(
    use_case: str,
    arguments: Sequence[str],
    runs_dir: Path | None,
    action: Callable[[RunRecord, PhaseTimings], int],
) -> int:
    parent = runs_dir if runs_dir is not None else USE_CASES_ROOT / use_case / "outputs"
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "_" + uuid4().hex[:8]
    directory = (parent / name).resolve()
    try:
        directory.mkdir(parents=True)
        with (directory / "run.log").open("w", encoding="utf-8") as log:
            with redirect_stderr(_LogStream(sys.stderr, log)):
                print(f"Run directory: {directory}", file=sys.stderr)
                record = RunRecord(directory, use_case, arguments)
                if "git_error" in record.code_context:
                    print(
                        f"Warning: code revision unavailable: {record.metadata['code']}",
                        file=sys.stderr,
                    )
                code = 1
                timings = PhaseTimings()
                try:
                    with log_run_timings() as timings:
                        code = action(record, timings)
                    return code
                finally:
                    record.finish(code, timings)
    except OSError as error:
        print(f"Error recording run '{directory}': {error}", file=sys.stderr)
        return 1


def generation_payload(generated: GeneratedSolution) -> dict[str, object]:
    specification = generated.specification
    config = specification.config
    return {
        "config": config.model_dump(mode="json"),
        "person_count": config.person_count,
        "element_cell_count": config.element_cell_count,
        "elements": [
            {
                "element": item.element.model_dump(mode="json"),
                "size": item.size,
                "count": item.count,
            }
            for item in specification.elements
        ],
        "map": generated.solution.map.model_dump(mode="json"),
        "placements": dict(generated.solution.placements),
        "victim": generated.victim,
        "furniture": [
            {"element": item.element, "cells": item.cells}
            for item in generated.furniture
        ],
    }
