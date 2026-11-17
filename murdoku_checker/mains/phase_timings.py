import sys
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter


class PhaseTimings:
    def __init__(self) -> None:
        self._durations: list[tuple[str, float]] = []
        self.total_seconds: float | None = None

    @property
    def durations(self) -> dict[str, float]:
        return dict(self._durations)

    @contextmanager
    def phase(self, name: str) -> Generator[None, None, None]:
        started = perf_counter()
        try:
            yield
        finally:
            self._durations.append((name, perf_counter() - started))

    def report(self, total: float) -> None:
        print("Phase timings:", file=sys.stderr)
        for name, duration in self._durations:
            print(f"  {name}: {duration:.6f} s", file=sys.stderr)
        print(f"  total: {total:.6f} s", file=sys.stderr)


@contextmanager
def log_run_timings() -> Generator[PhaseTimings, None, None]:
    started = perf_counter()
    timings = PhaseTimings()
    try:
        yield timings
    finally:
        timings.total_seconds = perf_counter() - started
        timings.report(timings.total_seconds)
