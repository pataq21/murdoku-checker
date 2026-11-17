from typing import Literal, Self

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator,
)


class ElementConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    size: Literal[1, 2]
    is_occupiable: StrictBool = False

    @field_validator("size", mode="before")
    @classmethod
    def validate_size_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("size must be an integer (1 or 2)")
        return value


RuleType = Literal[
    "in",
    "next_to",
    "not_next_to",
    "in_coordinate",
    "room_relation",
    "relative_position",
    "any_of",
]

ALL_RULE_TYPES: tuple[RuleType, ...] = (
    "in",
    "next_to",
    "not_next_to",
    "in_coordinate",
    "room_relation",
    "relative_position",
    "any_of",
)


class GenerationConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rows: int = Field(ge=1)
    columns: int = Field(ge=1)
    element_coverage_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    element_type_count: int = Field(ge=0)
    room_count: int = Field(ge=1)
    seed: int | None = None
    rule_types: tuple[RuleType, ...] = ALL_RULE_TYPES
    target_difficulty: int | None = Field(default=None, ge=0)
    person_names: tuple[str, ...] | None = None
    elements: dict[str, ElementConfig] | None = None

    @property
    def cell_count(self) -> int:
        return self.rows * self.columns

    @property
    def person_count(self) -> int:
        return min(self.rows, self.columns)

    @property
    def element_cell_count(self) -> int:
        """Round to the nearest integer, with ties going to the even integer."""
        return round(self.cell_count * self.element_coverage_percent / 100)

    @model_validator(mode="after")
    def validate_capacity(self) -> Self:
        if self.room_count > self.cell_count:
            raise ValueError("room_count cannot exceed the number of cells")
        if self.element_type_count > self.element_cell_count:
            raise ValueError(
                "not enough element cells for every element type to appear"
            )
        if self.element_cell_count > 0 and self.element_type_count == 0:
            raise ValueError("positive element coverage requires an element type")
        return self

    @model_validator(mode="after")
    def validate_names(self) -> Self:
        for field, names, count in (
            ("person_names", self.person_names, self.person_count),
        ):
            if names is None:
                continue
            if len(names) != count:
                raise ValueError(f"{field} must contain exactly {count} names")
            if any(not name.strip() for name in names):
                raise ValueError(f"{field} must contain non-empty names")
            if len(set(names)) != len(names):
                raise ValueError(f"{field} must contain unique names")
        return self

    @model_validator(mode="after")
    def validate_elements(self) -> Self:
        if self.elements is None:
            return self
        if len(self.elements) != self.element_type_count:
            raise ValueError(
                f"elements must contain exactly {self.element_type_count} entries"
            )
        if any(not name.strip() for name in self.elements):
            raise ValueError("elements must contain non-empty names")
        sizes = [element.size for element in self.elements.values()]
        if sum(sizes) > self.element_cell_count:
            raise ValueError("not enough element cells for the configured sizes")
        if sizes and 1 not in sizes and self.element_cell_count % 2:
            raise ValueError("size-2 elements cannot fill an odd element cell budget")
        return self
