import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from murdoku_checker.apps.pool_generator import generate_pool
from murdoku_checker.apps.problem_builder import build_problem
from murdoku_checker.apps.solution_creator import (
    generate_solution,
    generate_specification,
)
from murdoku_checker.domain import (
    Elements, Gender, MurdokuInput, People, Person, Rules,
)
from murdoku_checker.mains.phase_timings import PhaseTimings
from murdoku_checker.mains.run_recording import (
    RunRecord,
    add_run_arguments,
    generation_payload,
    run_recorded,
)
from murdoku_checker.mains.solution_display import format_generated_solution


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate an optimal clue subset with a unique solution."
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
        help="optional copy of the run's HTML solution at this path",
    )
    parser.add_argument(
        "--solver-logs",
        action="store_true",
        help="stream CP-SAT model, presolve and search logs to stderr",
    )
    add_run_arguments(parser)
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(arguments)
    if (
        args.format == "html"
        and args.output is not None
        and args.output.resolve() == args.config.resolve()
    ):
        parser.error("--output must not overwrite the input configuration")
    return run_recorded(
        "generate-puzzle",
        arguments,
        args.runs_dir,
        lambda record, timings: _run(args, timings, record),
    )


def _run(args: argparse.Namespace, timings: PhaseTimings, record: RunRecord) -> int:
    try:
        with timings.phase("load_config"):
            config = record.load_generation_config(args.config)
            if config.target_difficulty is None:
                raise ValueError("target_difficulty is required for generate-puzzle")
    except (OSError, ValueError) as error:
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
    payload = generation_payload(generated)
    result: dict[str, object] = {
        "config": payload["config"],
        "elements": payload["elements"],
        "solution": {
            key: payload[key] for key in ("map", "placements", "victim", "furniture")
        },
    }
    try:
        with timings.phase("generate_pool"):
            pool = generate_pool(
                generated.solution,
                victim=generated.victim,
                rule_types=config.rule_types,
            )
    except ValueError as error:
        print(f"Error generating clue pool: {error}", file=sys.stderr)
        return 1

    with timings.phase("log_pool_summary"):
        print("Generated rules per person:", file=sys.stderr)
        for person, rules in sorted(pool.items()):
            print(f"  {person}: total={len(rules)}", file=sys.stderr)
            for rule_type, count in sorted(Counter(rule.type for rule in rules).items()):
                print(f"    {rule_type}: {count}", file=sys.stderr)

    result["pool"] = Rules(
        rules=tuple(rule for rules in pool.values() for rule in rules)
    ).model_dump(mode="json")["rules"]
    try:
        with timings.phase("build_problem"):
            built = build_problem(
                MurdokuInput(
                    map=generated.solution.map,
                    elements=Elements(
                        elements=tuple(item.element for item in specification.elements)
                    ),
                    people=People(
                        people=tuple(
                            Person(
                                name=name,
                                gender=Gender.MALE,
                                is_victim=name == generated.victim,
                            )
                            for name in sorted(generated.solution.placements)
                        )
                    ),
                    rules=Rules(
                        rules=tuple(rule for rules in pool.values() for rule in rules)
                    ),
                ),
                generated.solution,
                victim=generated.victim,
                target_difficulty=config.target_difficulty,
                solver_logs=args.solver_logs,
            )
    except (ValueError, RuntimeError) as error:
        print(f"Error building puzzle: {error}", file=sys.stderr)
        return 1
    result["puzzle"] = built.puzzle.model_dump(mode="json")
    result["optimization"] = {
        "target_difficulty": config.target_difficulty,
        "total_difficulty": built.total_difficulty,
        "difficulty_error": built.difficulty_error,
        "rule_count": len(built.puzzle.rules.rules),
        "iterations": built.iterations,
    }
    try:
        with timings.phase("output"):
            content = record.save_generation(generated, result, rules=built.puzzle.rules)
            if args.format == "json":
                print(json.dumps(result, indent=2))
            elif args.format == "text":
                print(format_generated_solution(generated))
                print("\nClues:")
                for rule in built.puzzle.rules.rules:
                    print(f"- {rule.description}")
            else:
                output = args.output or record.directory / "solution.html"
                if args.output is not None:
                    output.write_text(content, encoding="utf-8")
                print(f"HTML solution written to '{output.resolve()}'")
                print(f"HTML puzzle written to '{record.directory / 'puzzle.html'}'")
    except OSError as error:
        print(f"Error writing puzzle output: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
