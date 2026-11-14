from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, Self

from ortools.sat.python import cp_model
from pydantic import Field, model_validator

from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.base_rule import BaseRule
from murdoku_checker.domain.rules.literals import any_of_literal
from murdoku_checker.domain.rules.targets import Target
from murdoku_checker.domain.solution import Solution

if TYPE_CHECKING:
    from murdoku_checker.domain.rules.rule import Rule


class AnyOfRule(BaseRule):
    """Disjunction: at least one of the nested rules holds.

    Nested rules refer to the same person; when given as raw data they may
    omit it and inherit it from the disjunction.
    """

    type: Literal["any_of"] = "any_of"
    conditions: tuple["Rule", ...] = Field(min_length=2, strict=False)

    @model_validator(mode="before")
    @classmethod
    def inherit_person(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or "person" not in data:
            return data
        conditions = data.get("conditions")
        if not isinstance(conditions, (list, tuple)):
            return data
        return {
            **data,
            "conditions": [
                {**condition, "person": data["person"]}
                if isinstance(condition, Mapping) and "person" not in condition
                else condition
                for condition in conditions
            ],
        }

    @model_validator(mode="after")
    def validate_same_person(self) -> Self:
        for condition in self.conditions:
            if condition.person != self.person:
                raise ValueError(
                    "any_of conditions must refer to the same person: "
                    f"{condition.person} != {self.person}"
                )
        return self

    @property
    def clause(self) -> str:
        return " or ".join(condition.clause for condition in self.conditions)

    @property
    def description(self) -> str:
        return f"Either {self.clause}."

    @property
    def difficulty(self) -> int:
        return 1 + sum(condition.difficulty for condition in self.conditions)

    @property
    def targets(self) -> tuple[Target, ...]:
        return tuple(
            target for condition in self.conditions for target in condition.targets
        )

    def evaluate(self, solution: Solution) -> bool:
        return any(condition.evaluate(solution) for condition in self.conditions)

    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        return any_of_literal(
            model,
            [condition.to_literal(model, variables) for condition in self.conditions],
        )

    def _condition_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            **data,
            "conditions": [condition["condition"] for condition in data["conditions"]],
        }
