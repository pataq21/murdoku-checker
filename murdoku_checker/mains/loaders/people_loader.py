from pathlib import Path

from murdoku_checker.domain import People


def load_people(path: str | Path) -> People:
    content = Path(path).read_text(encoding="utf-8")
    return People.model_validate_json(content)
