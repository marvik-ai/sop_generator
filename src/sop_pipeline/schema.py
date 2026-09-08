"""Pydantic mirror of the statement shapes in prompts/02_extract.md and
prompts/02_extract_folder.md, and of the conflict shape in prompts/07_reconcile.md.
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


class DocStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_section: TargetSection
    statement: str
    supporting_quote: str
    confidence: Confidence
    conflicts_with: str
    notes: str


class DocExtraction(BaseModel):
    """The wrapped shape actually returned by the API (see `pipeline._extract_one`)."""

    model_config = ConfigDict(extra="forbid")

    statements: list[DocStatement]


GapType = Literal["OPAQUE-RULE", "MISSING-DETAIL", "AMBIGUITY", "ASSUMPTION"]


class ConflictValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    source: str


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    values: list[ConflictValue]
    suggested_gap_type: GapType


class ReconcileOutput(BaseModel):
    """The wrapped shape actually returned by the API (see `pipeline.reconcile`)."""

    model_config = ConfigDict(extra="forbid")

    conflicts: list[Conflict]


class FolderStatement(DocStatement):
    """A statement extracted from a folder of related documents (02_extract_folder.md).

    A folder has several member files, so the model names the one its evidence came from;
    `supporting_media` is the timestamp range for a fact observed in a recording, "" for a
    text-only fact.
    """

    source: str
    supporting_media: str


class FolderExtraction(BaseModel):
    """The wrapped shape actually returned by the API (see `pipeline._extract_folder_one`)."""

    model_config = ConfigDict(extra="forbid")

    statements: list[FolderStatement]
