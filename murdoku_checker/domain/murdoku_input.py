from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from murdoku_checker.domain.elements import Elements
from murdoku_checker.domain.grid_cell import GridCell
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.people import People
from murdoku_checker.domain.rules import (
    FeatureElement,
    PersonElement,
    RoomElement,
    Rules,
)


class MurdokuInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    map: Map
    elements: Elements = Elements()
    people: People
    rules: Rules

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        person_names = {person.name for person in self.people.people}
        rooms = {room.name for room in self.map.rooms}
        element_names = {element.name for element in self.elements.elements}

        for cell in self.map.cells:
            for feature in cell.features:
                if feature not in element_names:
                    raise ValueError(f"unknown element in map: {feature}")

        for rule in self.rules.rules:
            if rule.person not in person_names:
                raise ValueError(f"unknown person in rule: {rule.person}")
            for target in rule.targets:
                if (
                    isinstance(target, PersonElement)
                    and target.value not in person_names
                ):
                    raise ValueError(f"unknown person in rule: {target.value}")
                if isinstance(target, RoomElement) and target.value not in rooms:
                    raise ValueError(f"unknown room in rule: {target.value}")
                if (
                    isinstance(target, FeatureElement)
                    and target.value not in element_names
                ):
                    raise ValueError(f"unknown feature in rule: {target.value}")

        return self

    def is_cell_occupiable(self, cell: GridCell) -> bool:
        for feature in cell.features:
            element = self.elements.get(feature)
            if element is None:
                raise ValueError(f"unknown element in map: {feature}")
            if not element.is_occupiable:
                return False
        return True
