import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from murdoku_checker.domain import Map
from murdoku_checker.loaders import load_map


def load_input_map(input_directory: Path) -> Map:
    return load_map(input_directory / "map.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load and validate a murdoku input directory."
    )
    parser.add_argument(
        "input_directory",
        type=Path,
        help="directory containing the input files, including map.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        map_ = load_input_map(args.input_directory)
    except (OSError, ValidationError) as error:
        print(
            f"Error loading input '{args.input_directory}': {error}",
            file=sys.stderr,
        )
        return 1

    map_path = args.input_directory / "map.json"
    print(f"Loaded map from '{map_path}' with {len(map_.cells)} cells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
