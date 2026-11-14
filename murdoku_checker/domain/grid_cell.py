from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from murdoku_checker.domain.element import ElementName

Coordinate = Annotated[int, Field(ge=0)]
RoomName = Annotated[str, Field(min_length=1)]
Position = tuple[int, int]


class GridCell(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    latitude: Coordinate
    longitude: Coordinate
    room: RoomName
    features: tuple[ElementName, ...] = Field(default=(), strict=False)

    @field_validator("features")
    @classmethod
    def validate_unique_features(
        cls, features: tuple[ElementName, ...]
    ) -> tuple[ElementName, ...]:
        if len(features) != len(set(features)):
            raise ValueError("duplicate cell feature")
        return features

    @property
    def position(self) -> Position:
        return (self.latitude, self.longitude)