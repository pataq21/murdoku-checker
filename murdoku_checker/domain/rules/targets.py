from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict

from murdoku_checker.domain.element import ElementName
from murdoku_checker.domain.grid_cell import RoomName
from murdoku_checker.domain.person import Name


class RoomElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["room"] = "room"
    value: RoomName


class FeatureElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["feature"] = "feature"
    value: ElementName


class PersonElement(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    type: Literal["person"] = "person"
    value: Name


Target: TypeAlias = RoomElement | FeatureElement | PersonElement
