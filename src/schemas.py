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

class ResearchArtifact(BaseModel):
    """Structured output for the Researcher node."""
    topic: str = Field(description="The core topic or query being researched.")
    findings: list[str] = Field(description="List of factual findings extracted from the research.")
    sources: list[str] = Field(description="List of sources or citations supporting the findings.")

class CoderArtifact(BaseModel):
    """Structured output for the Coder node."""
    file_name: str = Field(description="The name of the file being created or modified.")
    code: str = Field(description="The actual source code implementation.")
    explanation: str = Field(description="A brief explanation of how the code works and fulfills the objective.")
