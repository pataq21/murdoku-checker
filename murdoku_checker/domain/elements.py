from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from murdoku_checker.domain.element import Element


class Elements(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    elements: tuple[Element, ...] = Field(default=(), strict=False)
    _elements_by_name: Mapping[str, Element] = PrivateAttr(
        default_factory=lambda: MappingProxyType({})
    )

    @field_validator("elements")
    @classmethod
    def validate_unique_names(
        cls, elements: tuple[Element, ...]
    ) -> tuple[Element, ...]:
        names = [element.name for element in elements]
        if len(names) != len(set(names)):
            raise ValueError("duplicate element name")
        return elements

    def model_post_init(self, context: Any) -> None:
        self._elements_by_name = MappingProxyType(
            {element.name: element for element in self.elements}
        )

    def get(self, name: str) -> Element | None:
        return self._elements_by_name.get(name)