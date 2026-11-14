from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

ElementName = Annotated[str, Field(min_length=1)]


class Element(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: ElementName
    is_occupiable: StrictBool = False
