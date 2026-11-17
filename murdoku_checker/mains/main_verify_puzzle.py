import argparse
import sys
from collections.abc import Sequence
from html import escape
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.apps.solution_checker import check_solutions
from murdoku_checker.domain import Elements, Map, MurdokuInput, People, Rules
from murdoku_checker.mains.loaders import (
    load_elements,
    load_map,
    load_people,
    load_rules,
)
from murdoku_checker.mains.phase_timings import PhaseTimings
from murdoku_checker.mains.run_recording import (
    RunRecord,
    add_run_arguments,
    run_recorded,
)
from murdoku_checker.mains.solution_display import format_solution


def load_input_map(input_directory: Path) -> Map:
    return load_map(input_directory / "map.json")


def load_input_elements(input_directory: Path) -> Elements:
    return load_elements(input_directory / "elements.json")


def load_input_people(input_directory: Path) -> People:
    return load_people(input_directory / "people.json")


def load_input_rules(input_directory: Path) -> Rules:
    return load_rules(input_directory / "rules.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Solve a murdoku case, display its first solution and check uniqueness."
    )
    parser.add_argument(
        "input_directory",
        type=Path,
        help=(
            "directory containing the input files, including map.json, "
            "elements.json, people.json, and rules.json"
        ),
    )
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    add_run_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(arguments)
    return run_recorded(
        "verify-puzzle",
        arguments,
        args.runs_dir,
        lambda record, timings: _run(args, timings, record),
    )


def _run(args: argparse.Namespace, timings: PhaseTimings, record: RunRecord) -> int:
    try:
        with timings.phase("load_map"):
            snapshot = record.snapshot_puzzle(args.input_directory)
            map_ = load_input_map(snapshot)
        with timings.phase("load_elements"):
            elements = load_input_elements(snapshot)
        with timings.phase("load_people"):
            people = load_input_people(snapshot)
        with timings.phase("load_rules"):
            rules = load_input_rules(snapshot)
        with timings.phase("validate_input"):
            input_ = MurdokuInput(map=map_, elements=elements, people=people, rules=rules)
    except (OSError, ValidationError) as error:
        print(
            f"Error loading input '{args.input_directory}': {error}",
            file=sys.stderr,
        )
        return 1

    try:
        with timings.phase("check_solutions"):
            result = check_solutions(input_, solver_logs=args.solver_logs)
    except RuntimeError as error:
        print(f"Error solving input '{args.input_directory}': {error}", file=sys.stderr)
        return 1

    with timings.phase("output"):
        record.write_json(
            "result.json",
            {
                "count": result.count,
                "count_limit": 2,
                "first_solution": (
                    dict(result.first_solution)
                    if result.first_solution is not None else None
                ),
                "input": input_.model_dump(mode="json"),
            },
        )
        if result.first_solution is None:
            text = "No solution."
        else:
            status = (
                "Unique solution."
                if result.count == 1
                else "Multiple solutions (at least 2). Showing the first."
            )
            text = status + "\n" + format_solution(input_, result.first_solution)
        (record.directory / "solution.txt").write_text(text + "\n", encoding="utf-8")
        (record.directory / "solution.html").write_text(
            '<!doctype html>\n<html><head><meta charset="utf-8">'
            "<title>Murdoku verification</title></head>"
            f"<body><pre>{escape(text)}</pre></body></html>",
            encoding="utf-8",
        )
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
