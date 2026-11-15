from dataclasses import dataclass
from typing import Literal

from murdoku_checker.domain.element import Element
from murdoku_checker.domain.generation_config import GenerationConfig


@dataclass(frozen=True, slots=True)
class ElementSpecification:
    element: Element
    size: Literal[1, 2]
    count: int


@dataclass(frozen=True, slots=True)
class GenerationSpecification:
    """Unplaced element instances and the configuration for a future board."""

    config: GenerationConfig
    elements: tuple[ElementSpecification, ...]
