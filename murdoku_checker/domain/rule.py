from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from murdoku_checker.domain.cell import CellFeature
from murdoku_checker.domain.person import Name


class RoomElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["room"] = "room"
    value: Name


class FeatureElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["feature"] = "feature"
    value: CellFeature


class PersonElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["person"] = "person"
    value: Name


class Direction(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


Element: TypeAlias = Annotated[
    RoomElement | FeatureElement,
    Field(discriminator="type"),
]


class NextTo(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["next_to"] = "next_to"
    element: FeatureElement


class NotNextTo(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["not_next_to"] = "not_next_to"
    element: FeatureElement


class In(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["in"] = "in"
    element: Element
    is_unique: StrictBool = False


class RelativePosition(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["relative_position"] = "relative_position"
    direction: Direction
    element: PersonElement


class AnyOf(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["any_of"] = "any_of"
    conditions: tuple[Condition, ...] = Field(min_length=2, strict=False)


Condition: TypeAlias = Annotated[
    NextTo | NotNextTo | In | RelativePosition | AnyOf,
    Field(discriminator="type"),
]

AnyOf.model_rebuild(_types_namespace={"Condition": Condition})


class Rule(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    person: Name
    condition: Condition
