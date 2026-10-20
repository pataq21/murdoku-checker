from pydantic import BaseModel, ConfigDict, Field, field_validator

from murdoku_checker.domain.person import Person


class People(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    people: tuple[Person, ...] = Field(default=(), strict=False)

    @field_validator("people")
    @classmethod
    def validate_unique_names(cls, people: tuple[Person, ...]) -> tuple[Person, ...]:
        names: set[str] = set()
        for person in people:
            if person.name in names:
                raise ValueError(f"duplicate person name: {person.name}")
            names.add(person.name)
        return people
