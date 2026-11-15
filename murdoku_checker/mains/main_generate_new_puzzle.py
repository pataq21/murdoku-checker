import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.apps.solution_creator import generate_solution, generate_specification
from murdoku_checker.domain import GenerationConfig, Rules


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a target solution and its pool of true clues."
    )
    parser.add_argument("config", type=Path, help="generation configuration JSON file")
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    args = parser.parse_args(argv)

    try:
        config = GenerationConfig.model_validate_json(args.config.read_bytes())
    except (OSError, ValidationError) as error:
        print(f"Error loading generation config '{args.config}': {error}", file=sys.stderr)
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

    try:
        pool = generate_pool(generated.solution)
    except ValueError as error:
        print(f"Error generating clue pool: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "config": config.model_dump(mode="json"),
                "elements": [
                    {
                        "element": item.element.model_dump(mode="json"),
                        "size": item.size,
                        "count": item.count,
                    }
                    for item in specification.elements
                ],
                "solution": {
                    "map": generated.solution.map.model_dump(mode="json"),
                    "placements": dict(generated.solution.placements),
                    "victim": generated.victim,
                    "furniture": [
                        {"element": item.element, "cells": item.cells}
                        for item in generated.furniture
                    ],
                },
                "pool": Rules(rules=tuple(pool)).model_dump(mode="json")["rules"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
