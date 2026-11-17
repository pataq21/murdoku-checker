from random import Random
from typing import Literal

from murdoku_checker.apps.solution_creator.placement_model import PlacementModel
from murdoku_checker.domain.element import Element
from murdoku_checker.domain.generated_solution import GeneratedSolution
from murdoku_checker.domain.generation_config import GenerationConfig
from murdoku_checker.domain.generation_specification import (
    ElementSpecification,
    GenerationSpecification,
)


def generate_specification(config: GenerationConfig) -> GenerationSpecification:
    """Generate types and instance counts, without solving their placement."""
    random = Random(config.seed)
    type_count = config.element_type_count
    budget = config.element_cell_count

    if type_count == 0:
        return GenerationSpecification(config=config, elements=())

    max_large_types = min(type_count, budget - type_count)
    # An odd budget requires at least one size-one type to fill it exactly.
    if budget % 2:
        max_large_types = min(max_large_types, type_count - 1)
    large_types = set(
        random.sample(range(type_count), random.randint(0, max_large_types))
    )
    sizes: list[Literal[1, 2]] = [
        2 if index in large_types else 1 for index in range(type_count)
    ]
    counts = [1] * type_count
    remaining = budget - sum(sizes)
    while remaining:
        candidates = [
            index for index, size in enumerate(sizes) if size <= remaining
        ]
        index = random.choice(candidates)
        counts[index] += 1
        remaining -= sizes[index]

    elements = []
    for index, size in enumerate(sizes):
        configured = (
            config.element_names[index]
            if config.element_names is not None
            else f"element_{index + 1}"
        )
        occupiable = random.choice((False, True))
        element = (
            configured
            if isinstance(configured, Element)
            else Element(name=configured, is_occupiable=occupiable)
        )
        elements.append(
            ElementSpecification(element=element, size=size, count=counts[index])
        )
    return GenerationSpecification(config=config, elements=tuple(elements))


def generate_solution(
    specification: GenerationSpecification, *, solver_logs: bool = False
) -> GeneratedSolution | None:
    """Place the specification unchanged; None means it is infeasible."""
    return PlacementModel(specification).solve(solver_logs=solver_logs)
