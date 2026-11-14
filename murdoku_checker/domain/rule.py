from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from murdoku_checker.domain.cell import Coordinate
from murdoku_checker.domain.element import ElementName
from murdoku_checker.domain.person import Name


class RoomElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["room"] = "room"
    value: Name


class FeatureElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["feature"] = "feature"
    value: ElementName


class PersonElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["person"] = "person"
    value: Name


class Direction(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class FeatureTargetRelation(StrEnum):
    IN = "in"
    NEXT_TO = "next_to"


class RoomRelationKind(StrEnum):
    SAME = "same"
    DIFFERENT = "different"


class CoordinateAxis(StrEnum):
    ROW = "row"
    COLUMN = "column"


Element: TypeAlias = Annotated[
    RoomElement | FeatureElement,
    Field(discriminator="type"),
]

RelativeElement: TypeAlias = Annotated[
    PersonElement | FeatureElement,
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
    element: RelativeElement
    offset: Annotated[int, Field(ge=1)] | None = None
    feature_relation: FeatureTargetRelation = FeatureTargetRelation.IN

    @model_validator(mode="after")
    def validate_feature_relation(self) -> "RelativePosition":
        if (
            isinstance(self.element, PersonElement)
            and self.feature_relation is not FeatureTargetRelation.IN
        ):
            raise ValueError("feature_relation requires a feature element")
        return self


class RoomRelation(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["room_relation"] = "room_relation"
    relation: RoomRelationKind
    element: PersonElement


class InCoordinate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["in_coordinate"] = "in_coordinate"
    axis: CoordinateAxis
    value: Coordinate


class AnyOf(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["any_of"] = "any_of"
    conditions: tuple[Condition, ...] = Field(min_length=2, strict=False)


Condition: TypeAlias = Annotated[
    NextTo
    | NotNextTo
    | In
    | RelativePosition
    | RoomRelation
    | InCoordinate
    | AnyOf,
    Field(discriminator="type"),
]

AnyOf.model_rebuild(_types_namespace={"Condition": Condition})


class Rule(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    person: Name
    condition: Condition
