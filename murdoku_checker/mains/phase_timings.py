import sys
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter


class PhaseTimings:
    def __init__(self) -> None:
        self._durations: list[tuple[str, float]] = []

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
        timings.report(perf_counter() - started)
