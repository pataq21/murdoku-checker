from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from murdoku_checker.domain.cell import Cell
from murdoku_checker.domain.element import Elements
from murdoku_checker.domain.map import Map
from murdoku_checker.domain.people import People
from murdoku_checker.domain.rule import (
    AnyOf,
    Condition,
    FeatureElement,
    InCoordinate,
    NextToEmptyRoom,
    OtherRoomOccupied,
    PersonElement,
    RoomElement,
)
from murdoku_checker.domain.rules import Rules


class MurdokuInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    map: Map
    elements: Elements = Elements()
    people: People
    rules: Rules

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        person_names = {person.name for person in self.people.people}
        rooms = {cell.room for cell in self.map.cells}
        element_names = {element.name for element in self.elements.elements}

        for cell in self.map.cells:
            for feature in cell.features:
                if feature not in element_names:
                    raise ValueError(f"unknown element in map: {feature}")

        for rule in self.rules.rules:
            if rule.person not in person_names:
                raise ValueError(f"unknown person in rule: {rule.person}")
            self._validate_condition_references(
                rule.condition, rooms, element_names, person_names
            )

        return self

    @classmethod
    def _validate_condition_references(
        cls,
        condition: Condition,
        rooms: set[str],
        features: set[str],
        person_names: set[str],
    ) -> None:
        if isinstance(condition, AnyOf):
            for nested_condition in condition.conditions:
                cls._validate_condition_references(
                    nested_condition, rooms, features, person_names
                )
            return

        if isinstance(condition, InCoordinate):
            return

        if isinstance(condition, NextToEmptyRoom):
            return

        if isinstance(condition, OtherRoomOccupied):
            for room in condition.rooms:
                if room not in rooms:
                    raise ValueError(f"unknown room in rule: {room}")
            return

        element = condition.element
        if isinstance(element, PersonElement) and element.value not in person_names:
            raise ValueError(f"unknown person in rule: {element.value}")
        if isinstance(element, RoomElement) and element.value not in rooms:
            raise ValueError(f"unknown room in rule: {element.value}")
        if isinstance(element, FeatureElement) and element.value not in features:
            raise ValueError(f"unknown feature in rule: {element.value}")

    def is_cell_occupiable(self, cell: Cell) -> bool:
        for feature in cell.features:
            element = self.elements.get(feature)
            if element is None:
                raise ValueError(f"unknown element in map: {feature}")
            if not element.is_occupiable:
                return False
        return True
