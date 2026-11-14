from pathlib import Path

from murdoku_checker.domain import Elements


def load_elements(path: str | Path) -> Elements:
    content = Path(path).read_text(encoding="utf-8")
    return Elements.model_validate_json(content)
