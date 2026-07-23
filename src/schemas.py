"""Structured output contracts (report §5.7, §5.10, §7.4).

Schema validation guarantees that routing values are syntactically
valid graph transitions — free-form prose can never become a route.
"""

from typing import Literal

from pydantic import BaseModel, Field

class RouteDecision(BaseModel):
    """The Coordinator's only permitted output."""

    next: Literal["researcher", "coder", "reviewer", "finish"] = Field(
        description="The next worker to invoke, or 'finish' when the objective is satisfied."
    )
    reason: str = Field(
        description="One sentence explaining why this route was selected."
    )

class ReviewDecision(BaseModel):
    """The Reviewer's structured verdict (§5.10)."""

    verdict: Literal["pass", "revise", "escalate"]
    findings: list[str] = Field(default_factory=list)
    required_next_agent: Literal["researcher", "coder", "coordinator", "human"] = (
        "coordinator"
    )
