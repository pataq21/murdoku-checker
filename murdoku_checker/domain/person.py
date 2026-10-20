from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

Name = Annotated[str, Field(min_length=1)]


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"


class Person(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: Name
    gender: Gender
    wear_glasses: StrictBool = False
    is_bald: StrictBool = False
    is_victim: StrictBool = False
