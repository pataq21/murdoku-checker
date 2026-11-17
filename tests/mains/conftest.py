from pathlib import Path

import pytest

from murdoku_checker.mains import run_recording


@pytest.fixture(autouse=True)
def isolate_run_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_recording, "USE_CASES_ROOT", tmp_path / "use_cases")
