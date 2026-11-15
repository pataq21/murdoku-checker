from dataclasses import dataclass

from murdoku_checker.domain.generation_specification import GenerationSpecification
from murdoku_checker.domain.grid_cell import Position
from murdoku_checker.domain.solution import Solution


@dataclass(frozen=True, slots=True)
class FurniturePlacement:
    """One physical instance, distinct from other instances of the same type."""

    element: str
    cells: tuple[Position, ...]


@dataclass(frozen=True, slots=True)
class GeneratedSolution:
    specification: GenerationSpecification
    solution: Solution
    victim: str
    furniture: tuple[FurniturePlacement, ...]
