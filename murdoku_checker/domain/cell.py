from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

Coordinate = Annotated[int, Field(ge=0)]


class Cell(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    latitude: Coordinate
    longitude: Coordinate
    has_carpet: StrictBool = False
    has_plant: StrictBool = False
    has_sofa: StrictBool = False
    has_chair: StrictBool = False
