import argparse
import sys
from collections.abc import Sequence
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        map_ = load_input_map(args.input_directory)
        elements = load_input_elements(args.input_directory)
        people = load_input_people(args.input_directory)
        rules = load_input_rules(args.input_directory)
        input_ = MurdokuInput(map=map_, elements=elements, people=people, rules=rules)
    except (OSError, ValidationError) as error:
        print(
            f"Error loading input '{args.input_directory}': {error}",
            file=sys.stderr,
        )
        return 1

    try:
        result = check_solutions(input_, solver_logs=args.solver_logs)
    except RuntimeError as error:
        print(f"Error solving input '{args.input_directory}': {error}", file=sys.stderr)
        return 1

    if result.first_solution is None:
        print("No solution.")
    else:
        print(
            "Unique solution."
            if result.count == 1
            else "Multiple solutions (at least 2). Showing the first."
        )
        print(format_solution(input_, result.first_solution))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
