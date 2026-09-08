"""Pydantic mirrors of the statement shapes the extraction prompts return.

`VideoStatement` is the unit every strategy produces (prompts/02_extract_video*.md);
`SequentialChunkOutput` is the per-chunk envelope the sequential strategy carries state in.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


TargetSection = Literal[
    "scope",
    "glossary",
    "systems",
    "process_overview",
    "step",
    "business_rule",
    "error_handling",
    "end_state",
    "gap",
    "decision",
]
Confidence = Literal["high", "medium", "low"]


class VideoStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_section: TargetSection
    statement: str
    supporting_quote: str
    supporting_media: str
    confidence: Confidence
    conflicts_with: str
    notes: str


class VideoExtraction(BaseModel):
    """The wrapped shape actually returned by the API (see `naive.extract`)."""

    model_config = ConfigDict(extra="forbid")

    statements: list[VideoStatement]


class VideoExtractionChunk(BaseModel):
    """One chunk's answer in the sequential strategy: new facts plus the state to carry forward.

    `statements` holds what this chunk added or corrected. `ui_state`, `open_questions`,
    and `resolved` together are the running state: the screen at the chunk's end, what's
    still unresolved, and what this chunk closed. Every field is required, as OpenAI's
    strict Structured Outputs demands (see `llm.complete`).
    """

    model_config = ConfigDict(extra="forbid")

    statements: list[VideoStatement]
    ui_state: str
    open_questions: list[str]
    resolved: list[str]
