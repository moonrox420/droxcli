"""Pydantic models for the intent parsing step."""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Intent(BaseModel):
    action: Literal["create", "refactor", "fix", "delete", "rename", "plan", "complete"]
    target_files: List[str] = Field(default_factory=list)
    description: str
    language: Literal["python", "js", "go", "yaml", "toml", "json", "any"] = "any"
    tests_needed: bool = False
    dry_run: bool = False
