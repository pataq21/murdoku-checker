import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.apps.solution_creator import (
    generate_solution,
    generate_specification,
)
from murdoku_checker.domain import GenerationConfig
from murdoku_checker.mains.solution_display import format_generated_solution
from murdoku_checker.mains.solution_display_html import format_solution_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a murdoku solution with connected rooms, furniture "
            "and person placements."
        )
    )
    parser.add_argument(
        "config",
        type=Path,
        help="path to the generation configuration JSON file",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text", "html"),
        default="json",
        help="output format: json, text grid or standalone HTML (default: json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="destination file (required for HTML, only supported with --format html)",
    )
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.format == "html" and args.output is None:
        parser.error("--format html requires --output")
    if args.format != "html" and args.output is not None:
        parser.error("--output is only supported with --format html")
    if args.output is not None and args.output.resolve() == args.config.resolve():
        parser.error("--output must not overwrite the input configuration")

    try:
        config = GenerationConfig.model_validate_json(args.config.read_bytes())
    except (OSError, ValidationError) as error:
        print(
            f"Error loading generation config '{args.config}': {error}",
            file=sys.stderr,
        )
        return 1

    specification = generate_specification(config)
    try:
        generated = generate_solution(specification, solver_logs=args.solver_logs)
    except RuntimeError as error:
        print(f"Error generating solution: {error}", file=sys.stderr)
        return 1
    if generated is None:
        print(
            "No solution for the generated specification. "
            "Parameters and element properties were not changed.",
            file=sys.stderr,
        )
        return 1

    if args.format == "text":
        print(format_generated_solution(generated))
        return 0
    if args.format == "html":
        content = format_solution_html(generated)
        try:
            args.output.write_text(content, encoding="utf-8")
        except OSError as error:
            print(f"Error writing HTML solution '{args.output}': {error}", file=sys.stderr)
            return 1
        print(f"HTML solution written to '{args.output.resolve()}'")
        return 0

    print(
        json.dumps(
            {
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
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
