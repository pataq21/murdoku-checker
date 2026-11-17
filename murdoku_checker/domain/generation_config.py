from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
