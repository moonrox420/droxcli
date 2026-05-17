"""Pydantic models for the Ollama planning + execution pipeline."""

from pydantic import BaseModel, Field, field_validator
from typing import List

_OP_SYNONYMS = {
    "create": "add",
    "new": "add",
    "write": "add",
    "run": "edit",
    "execute": "edit",
    "update": "edit",
    "modify": "edit",
    "delete": "remove",
    "drop": "remove",
    "destroy": "remove",
}


class PlanStep(BaseModel):
    step_id: int
    description: str
    operation: str = "edit"
    file: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("operation", mode="before")
    @classmethod
    def normalise_operation(cls, v: str) -> str:
        v = str(v).lower().strip()
        if v in {"edit", "add", "remove"}:
            return v
        return _OP_SYNONYMS.get(v, "edit")


class Plan(BaseModel):
    steps: List[PlanStep]
    overall_estimated_tokens: int = 0
    token_budget_ok: bool = True


class DiffPatch(BaseModel):
    file: str
    original: str = ""
    new: str
    summary: str = ""
