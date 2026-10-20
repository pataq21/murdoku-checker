from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Coordinate = Annotated[int, Field(ge=0)]
Room = Annotated[str, Field(min_length=1)]


class CellFeature(StrEnum):
    BED = "bed"
    BOX = "box"
    CARPET = "carpet"
    CHAIR = "chair"
    COUNTER = "counter"
    PLANT = "plant"
    TABLE = "table"
    TREE = "tree"
    WARDROBE = "wardrobe"


class Cell(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    latitude: Coordinate
    longitude: Coordinate
    room: Room
    features: tuple[CellFeature, ...] = Field(default=(), strict=False)

    @field_validator("features")
    @classmethod
    def validate_unique_features(
        cls, features: tuple[CellFeature, ...]
    ) -> tuple[CellFeature, ...]:
        if len(features) != len(set(features)):
            raise ValueError("duplicate cell feature")
        return features
