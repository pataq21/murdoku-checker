from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from murdoku_checker.domain.element import ElementName

Coordinate = Annotated[int, Field(ge=0)]
Room = Annotated[str, Field(min_length=1)]


class Cell(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    latitude: Coordinate
    longitude: Coordinate
    room: Room
    features: tuple[ElementName, ...] = Field(default=(), strict=False)

    @field_validator("features")
    @classmethod
    def validate_unique_features(
        cls, features: tuple[ElementName, ...]
    ) -> tuple[ElementName, ...]:
        if len(features) != len(set(features)):
            raise ValueError("duplicate cell feature")
        return features
