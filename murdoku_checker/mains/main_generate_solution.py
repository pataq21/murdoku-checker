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
from murdoku_checker.mains.phase_timings import PhaseTimings
from murdoku_checker.mains.run_recording import (
    RunRecord,
    add_run_arguments,
    generation_payload,
    run_recorded,
)
from murdoku_checker.mains.solution_display import format_generated_solution


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
        help="optional HTML copy (only supported with --format html)",
    )
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    add_run_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(arguments)
    if args.format != "html" and args.output is not None:
        parser.error("--output is only supported with --format html")
    if args.output is not None and args.output.resolve() == args.config.resolve():
        parser.error("--output must not overwrite the input configuration")
    return run_recorded(
        "generate-solution",
        arguments,
        args.runs_dir,
        lambda record, timings: _run(args, timings, record),
    )


def _run(args: argparse.Namespace, timings: PhaseTimings, record: RunRecord) -> int:
    try:
        with timings.phase("load_config"):
            config = record.load_generation_config(args.config)
    except (OSError, ValidationError) as error:
        print(
            f"Error loading generation config '{args.config}': {error}",
            file=sys.stderr,
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
        with timings.phase("output"):
            record.save_generation(generated, generation_payload(generated))
            print(format_generated_solution(generated))
        return 0
    if args.format == "html":
        try:
            with timings.phase("output"):
                content = record.save_generation(generated, generation_payload(generated))
                output = args.output or record.directory / "solution.html"
                if args.output is not None:
                    output.write_text(content, encoding="utf-8")
                print(f"HTML solution written to '{output.resolve()}'")
        except OSError as error:
            print(f"Error writing HTML solution '{args.output}': {error}", file=sys.stderr)
            return 1
        return 0

    with timings.phase("output"):
        result = generation_payload(generated)
        record.save_generation(generated, result)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
