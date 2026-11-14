from pathlib import Path

from murdoku_checker.domain import Rules


def load_rules(path: str | Path) -> Rules:
    content = Path(path).read_text(encoding="utf-8")
    return Rules.model_validate_json(content)
