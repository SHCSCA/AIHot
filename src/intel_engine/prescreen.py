from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PreScreenDecision(BaseModel):
    bucket: Literal["relevant", "maybe", "irrelevant"]
    is_relevant: bool
    reason: str
    signals: list[str] = Field(default_factory=list)
