from pydantic import BaseModel, ConfigDict, Field

from murdoku_checker.domain.rule import Rule


class Rules(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    rules: tuple[Rule, ...] = Field(default=(), strict=False)
