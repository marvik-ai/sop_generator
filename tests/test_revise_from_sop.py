"""Unit tests for the SOP-revision route (--sop): no API, no assumptions about any real
SOP template — just that supplying an existing SOP switches the pipeline onto the
overlay prompts and drops the SOP file from the raw-extraction corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from sop_pipeline import pipeline
from sop_pipeline.ingest import SourceDoc
from sop_pipeline.pipeline import _without_existing_sop
from sop_pipeline.prompts import load_prompt, render


_FAKE_SOP = "# SOP — Fake process\n\nSome existing content.\n"


def test_reconcile_uses_the_renewal_prompt_only_with_a_sop(monkeypatch):
    captured: dict[str, str] = {}

    def fake_complete(prompt, **_kwargs):
        captured["prompt"] = prompt
        return '{"conflicts": []}'

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)

    pipeline.reconcile([{"statement": "x", "source": "a.md"}], existing_sop=_FAKE_SOP)
    with_sop_prompt = captured["prompt"]
    assert _FAKE_SOP in with_sop_prompt
    assert "Overlay: reconciling against an existing SOP" in with_sop_prompt

    statements = [{"statement": "x", "source": "a.md"}]
    pipeline.reconcile(statements)
    without_sop_prompt = captured["prompt"]
    assert "Overlay: reconciling against an existing SOP" not in without_sop_prompt
    assert "{{EXISTING_SOP}}" not in without_sop_prompt
    # The no-SOP prompt is exactly the base template rendered as before: no overlay text,
    # nothing appended.
    expected = render(
        load_prompt("07_reconcile.md"),
        STATEMENTS_JSON=json.dumps(statements, ensure_ascii=False, indent=2),
    )
    assert without_sop_prompt == expected


def test_synthesize_uses_the_renewal_prompt_only_with_a_sop(monkeypatch):
    captured: dict[str, str] = {}

    def fake_complete(prompt, **_kwargs):
        captured["prompt"] = prompt
        return "# SOP body"

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)

    pipeline.synthesize([], "schema guide text", existing_sop=_FAKE_SOP)
    with_sop_prompt = captured["prompt"]
    assert _FAKE_SOP in with_sop_prompt
    assert "Overlay: revising an existing SOP" in with_sop_prompt

    pipeline.synthesize([], "schema guide text")
    without_sop_prompt = captured["prompt"]
    assert "Overlay: revising an existing SOP" not in without_sop_prompt
    assert "{{EXISTING_SOP}}" not in without_sop_prompt


def test_without_existing_sop_drops_the_sop_from_the_corpus(tmp_path: Path):
    sop_file = tmp_path / "sop.md"
    sop_file.write_text(_FAKE_SOP, encoding="utf-8")
    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("some notes", encoding="utf-8")

    docs = [
        SourceDoc(name="sop.md", text=_FAKE_SOP),
        SourceDoc(name="notes.txt", text="some notes"),
    ]

    filtered = _without_existing_sop(docs, tmp_path, sop_file)
    assert [d.name for d in filtered] == ["notes.txt"]


def test_without_existing_sop_is_a_noop_without_a_sop_path(tmp_path: Path):
    docs = [SourceDoc(name="notes.txt", text="some notes")]
    assert _without_existing_sop(docs, tmp_path, None) == docs


def test_without_existing_sop_keeps_everything_when_sop_lives_outside_inputs(
    tmp_path: Path,
):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_sop = outside_dir / "sop.md"
    outside_sop.write_text(_FAKE_SOP, encoding="utf-8")

    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir()
    docs = [SourceDoc(name="notes.txt", text="some notes")]

    assert _without_existing_sop(docs, inputs_dir, outside_sop) == docs
