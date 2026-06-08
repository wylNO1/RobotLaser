"""Robot metadata shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JointLimit(BaseModel):
    lower: float | None = None
    upper: float | None = None
    effort: float | None = None
    velocity: float | None = None


class JointMeta(BaseModel):
    name: str
    type: str
    parent: str
    child: str
    axis: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0])
    limit: JointLimit | None = None
