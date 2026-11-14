from collections.abc import Mapping
from typing import Annotated, Any, TypeAlias

from pydantic import BeforeValidator, Field, TypeAdapter

from murdoku_checker.domain.rules.any_of import AnyOfRule
from murdoku_checker.domain.rules.in_coordinate import InCoordinateRule
from murdoku_checker.domain.rules.in_rule import InRule
from murdoku_checker.domain.rules.next_to import NextToRule
from murdoku_checker.domain.rules.not_next_to import NotNextToRule
from murdoku_checker.domain.rules.relative_position import RelativePositionRule
from murdoku_checker.domain.rules.room_relation import RoomRelationRule


def _lift_condition(data: Any) -> Any:
    """Accept the rules.json shape {"person": ..., "condition": {...}}."""
    if not isinstance(data, Mapping) or "condition" not in data:
        return data
    condition = data["condition"]
    if not isinstance(condition, Mapping) or "person" in condition:
        return data
    return {
        **condition,
        **{key: value for key, value in data.items() if key != "condition"},
    }


Rule: TypeAlias = Annotated[
    NextToRule
    | NotNextToRule
    | InRule
    | RelativePositionRule
    | RoomRelationRule
    | InCoordinateRule
    | AnyOfRule,
    Field(discriminator="type"),
    BeforeValidator(_lift_condition),
]

AnyOfRule.model_rebuild(_types_namespace={"Rule": Rule})

RULE_ADAPTER: TypeAdapter[Rule] = TypeAdapter(Rule)
