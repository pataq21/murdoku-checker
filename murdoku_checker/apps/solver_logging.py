import sys

from ortools.sat.python import cp_model


def _write_solver_log(message: str) -> None:
    print(message.rstrip("\n"), file=sys.stderr, flush=True)


def configure_solver_logging(solver: cp_model.CpSolver, enabled: bool) -> None:
    """Stream CP-SAT diagnostics without mixing them into application stdout."""
    solver.parameters.log_search_progress = enabled
    solver.parameters.log_to_stdout = False
    solver.log_callback = _write_solver_log if enabled else None
