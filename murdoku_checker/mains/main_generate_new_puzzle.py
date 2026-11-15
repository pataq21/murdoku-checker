import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.apps.solution_creator import (
    generate_solution,
    generate_specification,
)
from murdoku_checker.domain import GenerationConfig
from murdoku_checker.mains.phase_timings import PhaseTimings, log_run_timings
from murdoku_checker.mains.solution_display import format_generated_solution
from murdoku_checker.mains.solution_display_html import format_solution_html


def main(argv: Sequence[str] | None = None) -> int:
    with log_run_timings() as timings:
        return _run(argv, timings)


def _run(argv: Sequence[str] | None, timings: PhaseTimings) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a target solution and its pool of true clues."
    )
    parser.add_argument("config", type=Path, help="generation configuration JSON file")
    parser.add_argument(
        "--format",
        choices=("json", "text", "html"),
        default="json",
        help="output format: json, text grid or standalone HTML (default: json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("solution.html"),
        help="output file for HTML format (default: solution.html)",
    )
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    args = parser.parse_args(argv)

    try:
        with timings.phase("load_config"):
            config = GenerationConfig.model_validate_json(args.config.read_bytes())
    except (OSError, ValidationError) as error:
        print(
            f"Error loading generation config '{args.config}': {error}", file=sys.stderr
        )
        return 1

    with timings.phase("generate_specification"):
        specification = generate_specification(config)
    try:
        with timings.phase("generate_solution"):
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
        try:
            content = format_solution_html(generated)
            args.output.write_text(content, encoding="utf-8")
            print(f"HTML solution written to '{args.output.resolve()}'")
        except OSError as error:
            print(
                f"Error writing HTML solution '{args.output}': {error}", file=sys.stderr
            )
            return 1
    try:
        with timings.phase("generate_pool"):
            pool = generate_pool(generated.solution, victim=generated.victim)
    except ValueError as error:
        print(f"Error generating clue pool: {error}", file=sys.stderr)
        return 1

    print("Generated rules per person:", file=sys.stderr)
    for person, rules in sorted(pool.items()):
        print(f"  {person}: total={len(rules)}", file=sys.stderr)
        for rule_type, count in sorted(Counter(rule.type for rule in rules).items()):
            print(f"    {rule_type}: {count}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
