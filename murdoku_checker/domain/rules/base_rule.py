from abc import ABC, abstractmethod
from typing import Any

from ortools.sat.python import cp_model
from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from murdoku_checker.domain.person import Name
from murdoku_checker.domain.placement_variables import PlacementVariables
from murdoku_checker.domain.rules.targets import PersonElement, Target
from murdoku_checker.domain.solution import Solution


class BaseRule(BaseModel, ABC):
    """Clue about where a person is (Strategy pattern).

    Each concrete rule knows how to describe itself to the player, how hard it
    is to use, whether it holds in a given solution and how to express itself
    as CP-SAT constraints.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    person: Name

    @property
    @abstractmethod
    def clause(self) -> str:
        """Description without the final period, to be composed in sentences."""

    @property
    def description(self) -> str:
        """Clue text shown to the player."""
        return f"{self.clause}."

    @property
    @abstractmethod
    def difficulty(self) -> int:
        """Cognitive cost of applying the clue; higher is harder."""

    @property
    def targets(self) -> tuple[Target, ...]:
        """Rooms, features and people referenced by the rule."""
        return ()

    @property
    def protagonists(self) -> frozenset[str]:
        """People involved in the clue."""
        return frozenset(
            {self.person}
            | {
                target.value
                for target in self.targets
                if isinstance(target, PersonElement)
            }
        )

    @abstractmethod
    def evaluate(self, solution: Solution) -> bool:
        """Whether the rule holds in the given solution."""

    @abstractmethod
    def to_literal(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> cp_model.IntVar:
        """Boolean variable that is true exactly when the rule holds.

        Used to compose rules, for instance inside disjunctions.
        """

    def apply_to_model(
        self, model: cp_model.CpModel, variables: PlacementVariables
    ) -> None:
        """Add the constraints enforcing the rule to the CP-SAT model."""
        model.add_bool_and([self.to_literal(model, variables)])

    def _condition_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    @model_serializer(mode="wrap")
    def _serialize_as_condition(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        # Keep the rules.json shape: {"person": ..., "condition": {...}}.
        data = dict(handler(self))
        if "condition" in data:
            # Already reshaped: pydantic may apply this serializer twice when
            # the rule is wrapped by an annotated union.
            return data
        person = data.pop("person")
        return {"person": person, "condition": self._condition_payload(data)}
