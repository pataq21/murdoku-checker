import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.domain import Map, MurdokuInput, People, Rules
from murdoku_checker.loaders import load_map, load_people, load_rules
from murdoku_checker.optimization import ModelBuilder
from murdoku_checker.solution_display import format_solution


def load_input_map(input_directory: Path) -> Map:
    return load_map(input_directory / "map.json")


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
            "people.json, and rules.json"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        map_ = load_input_map(args.input_directory)
        people = load_input_people(args.input_directory)
        rules = load_input_rules(args.input_directory)
        input_ = MurdokuInput(map=map_, people=people, rules=rules)
    except (OSError, ValidationError) as error:
        print(
            f"Error loading input '{args.input_directory}': {error}",
            file=sys.stderr,
        )
        return 1

    try:
        optimization_model = ModelBuilder().build(input_)
        result = optimization_model.solve_with_solution(max_solutions=2)
    except RuntimeError as error:
        print(f"Error solving input '{args.input_directory}': {error}", file=sys.stderr)
        return 1

    map_path = args.input_directory / "map.json"
    people_path = args.input_directory / "people.json"
    rules_path = args.input_directory / "rules.json"
    print(f"Loaded map from '{map_path}' with {len(input_.map.cells)} cells.")
    print(
        f"Loaded people from '{people_path}' with {len(input_.people.people)} people."
    )
    print(f"Loaded rules from '{rules_path}' with {len(input_.rules.rules)} rules.")
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
