from pathlib import Path

from murdoku_checker.domain import Map


def load_map(path: str | Path) -> Map:
    content = Path(path).read_text(encoding="utf-8")
    return Map.model_validate_json(content)