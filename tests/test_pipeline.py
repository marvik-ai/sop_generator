"""Unit tests for the pure (no-API) helpers in the pipeline module."""

from __future__ import annotations

import types
from pathlib import Path

from sop_pipeline import mermaid, pipeline
from sop_pipeline.ingest import SourceDoc
from sop_pipeline.llm import parse_json_array
from sop_pipeline.pipeline import (
    _appendix_a,
    _cached_statements,
    _diagram_advisory,
    _front_matter,
    _harvest_checkpoints,
    _normalize_section1,
    _slugify,
    _statements_hash,
    _table_of_contents,
    _validation_warnings_md,
    _write_cache,
)


_META = {
    "run_date": "2026-06-29",
    "author": "Marvik",
    "version": "0.1 (draft)",
    "status": "Draft",
}


# --- parse_json_array -------------------------------------------------------


def test_parse_bare_array():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_parse_json_fenced_block():
    raw = '```json\n[{"a": 1}, {"b": 2}]\n```'
    assert parse_json_array(raw) == [{"a": 1}, {"b": 2}]


def test_parse_array_wrapped_in_prose():
    raw = 'Here are the statements:\n[{"a": 1}]\nThanks!'
    assert parse_json_array(raw) == [{"a": 1}]


def test_parse_malformed_returns_empty():
    assert parse_json_array("not json at all") == []
    assert parse_json_array("") == []


# --- _statements_hash --------------------------------------------------------


def test_hash_is_stable_for_identical_input():
    stmts = [{"statement": "x", "source": "a"}]
    assert _statements_hash(stmts, "prompt") == _statements_hash(stmts, "prompt")


def test_hash_is_key_order_insensitive():
    a = [{"statement": "x", "source": "a"}]
    b = [{"source": "a", "statement": "x"}]
    assert _statements_hash(a, "prompt") == _statements_hash(b, "prompt")


def test_hash_changes_with_content():
    base = [{"statement": "x"}]
    other = [{"statement": "y"}]
    assert _statements_hash(base, "prompt") != _statements_hash(other, "prompt")


def test_hash_changes_with_prompt_salt():
    stmts = [{"statement": "x"}]
    assert _statements_hash(stmts, "prompt A") != _statements_hash(stmts, "prompt B")


# --- extraction cache is prompt-aware ---------------------------------------


def test_extraction_cache_hits_with_same_prompt(tmp_path):
    doc = SourceDoc(name="doc.md", text="hello")
    stmts = [{"statement": "x"}]
    _write_cache(tmp_path, doc, "prompt A", stmts)
    assert _cached_statements(tmp_path, doc, "prompt A") == stmts


def test_extraction_cache_misses_when_prompt_changes(tmp_path):
    doc = SourceDoc(name="doc.md", text="hello")
    _write_cache(tmp_path, doc, "prompt A", [{"statement": "x"}])
    # Same file content, different extract prompt -> stale, must miss.
    assert _cached_statements(tmp_path, doc, "prompt B") is None


# --- _normalize_section1 -----------------------------------------------------


def test_normalize_fills_metadata_and_strips_section1_gap_tags():
    md = (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        "| Last updated | [GAP G-03] |\n"
        "| Author / owner | [GAP G-04] |\n"
        "| Status | Draft |\n\n"
        "## 2. Purpose\n\nbody\n"
    )
    out = _normalize_section1(md, _META)
    assert "| Last updated | 2026-06-29 |" in out
    assert "| Author / owner | Marvik |" in out
    assert "[GAP" not in out.split("## 2.")[0]  # no gap tags left in Section 1


def test_normalize_leaves_body_gaps_untouched():
    md = (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        "| Author / owner | Marvik |\n\n"
        "## 6. Steps\n\nStep 2 reads Applicability [GAP G-01].\n"
    )
    out = _normalize_section1(md, _META)
    assert "[GAP G-01]" in out  # body gap preserved


def test_normalize_is_noop_on_clean_section1():
    # No trailing newline: splitlines()/join round-trips exactly when already clean.
    md = (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        "| Last updated | 2026-06-29 |\n"
        "| Author / owner | Marvik |\n\n"
        "## 2. Purpose\n\nbody"
    )
    assert _normalize_section1(md, _META) == md


# --- _slugify -----------------------------------------------------------------


def test_slugify_matches_north_star_section_anchor():
    assert _slugify("1. Document control / metadata") == "1-document-control--metadata"


def test_slugify_matches_north_star_annex_anchor():
    assert _slugify("Annex 1: Mermaid diagram") == "annex-1-mermaid-diagram"


def test_slugify_matches_north_star_appendix_anchor():
    assert (
        _slugify("Appendix A: Machine-readable evaluation checkpoint index")
        == "appendix-a-machine-readable-evaluation-checkpoint-index"
    )


# --- _table_of_contents --------------------------------------------------------


def test_toc_numbers_sections_and_bullets_unnumbered_headings():
    md = (
        "## 1. Document control / metadata\n\nbody1\n\n"
        "## 2. Purpose & scope\n\nbody2\n\n"
        "## Annex 1: Mermaid diagram\n\n```mermaid\n```\n"
    )
    toc = _table_of_contents(md)
    assert "1. [Document control / metadata](#1-document-control--metadata)" in toc
    assert "2. [Purpose & scope](#2-purpose--scope)" in toc
    assert "- [Annex 1: Mermaid diagram](#annex-1-mermaid-diagram)" in toc


# --- _front_matter --------------------------------------------------------------


def test_front_matter_pulls_title_and_metadata():
    md = (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        "| SOP title | Standalone Unpaid Absence — Adjudication |\n"
        "| Last updated | 2026-06-29 |\n\n"
        "## 2. Purpose\n\nbody"
    )
    front = _front_matter(md, _META)
    assert front.startswith("# SOP — Standalone Unpaid Absence — Adjudication")
    assert "**June 2026**" in front
    assert "Completeness note" in front


def test_front_matter_omits_month_year_when_run_date_unparsable():
    md = (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        "| SOP title | X |\n\n"
        "## 2. Purpose\n\nbody"
    )
    meta = dict(_META, run_date="TBD")
    front = _front_matter(md, meta)
    lines = front.splitlines()
    assert lines[:2] == ["# SOP — X", ""]
    assert lines[2] == "**Prepared for:** MyAwesomeCompany"  # no month/year line inserted
    assert "TBD" not in front  # no stray placeholder leaked into the front matter


# --- _harvest_checkpoints -------------------------------------------------------


_TWO_STEP_SOP = (
    "## 6. Step-by-step procedure\n\n"
    "### Step 1 — Intake\n\n"
    "- **Goal (plain language):** do the thing.\n"
    "- **Evaluation checkpoints:**\n"
    "  - Every leave plan received exactly one classification.\n"
    "  - The request was normalized before routing.\n"
    "- **Open questions / gaps:** G-01, G-02\n\n"
    "### Step 2 — Eligibility\n\n"
    "- **Evaluation checkpoints:**\n"
    "  - Each active plan's eligibility result was classified.\n"
    "- **Open questions / gaps:** None\n\n"
    "## 7. Business rules reference\n\nirrelevant\n"
)


def test_harvest_checkpoints_assigns_stable_ids():
    checkpoints = _harvest_checkpoints(_TWO_STEP_SOP)
    ids = [cp["id"] for cp in checkpoints]
    assert ids == ["STEP1-C1", "STEP1-C2", "STEP2-C1"]


def test_harvest_checkpoints_extracts_related_gaps():
    checkpoints = _harvest_checkpoints(_TWO_STEP_SOP)
    by_id = {cp["id"]: cp for cp in checkpoints}
    assert by_id["STEP1-C1"]["related_gaps"] == "G-01, G-02"
    assert by_id["STEP2-C1"]["related_gaps"] == "—"


def test_harvest_checkpoints_scope_heuristic():
    # Scope isn't part of the checkpoint dict itself (computed in _appendix_a) — confirm
    # the table rendering picks the per-plan label for the "every/each ... plan" bullets.
    checkpoints = _harvest_checkpoints(_TWO_STEP_SOP)
    appendix = _appendix_a(checkpoints, "### Cross-cutting invariants\n\n(none)")
    assert "| STEP1-C1 | 1 | Per-plan |" in appendix
    assert "| STEP2-C1 | 2 | Per-plan |" in appendix


# --- _appendix_a ----------------------------------------------------------------


def test_appendix_a_includes_total_and_invariants():
    checkpoints = _harvest_checkpoints(_TWO_STEP_SOP)
    appendix = _appendix_a(checkpoints, "### Cross-cutting invariants\n\n(placeholder)")
    assert "**Total checkpoints: 3**" in appendix
    assert "### Cross-cutting invariants" in appendix
    assert "(placeholder)" in appendix


# --- validation-warning persistence --------------------------------------------------


def test_validation_warnings_md_groups_both_kinds():
    section = _validation_warnings_md(
        ["Section 12 row G-03 is never referenced in the body."],
        [
            "End state 'Technical error' from Section 11 has no terminal node in the diagram."
        ],
    )
    assert "## Deterministic validation warnings" in section
    assert "### Gap-ID & fork-branch checks" in section
    assert "- Section 12 row G-03 is never referenced in the body." in section
    assert "### Flow-diagram parity (Annex 1)" in section
    assert "- End state 'Technical error'" in section


def test_validation_warnings_md_states_clean_when_empty():
    section = _validation_warnings_md([], [])
    assert "## Deterministic validation warnings" in section
    assert "No deterministic validation warnings." in section
    assert "### Gap-ID" not in section
    assert "### Flow-diagram" not in section


def test_validation_warnings_md_omits_empty_group():
    section = _validation_warnings_md([], ["a diagram warning"])
    assert "### Flow-diagram parity (Annex 1)" in section
    assert "### Gap-ID & fork-branch checks" not in section


def test_diagram_advisory_present_only_when_warnings():
    assert _diagram_advisory([]) == ""
    note = _diagram_advisory(["Step 7 declares 4 IF/THEN branch(es) but node S7 ..."])
    assert note.startswith("> ⚠️")
    assert "gaps_report.md" in note
    assert note.endswith("\n\n")


# --- mermaid render/validate wrapper -------------------------------------------------


def test_render_skips_when_mmdc_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(mermaid.shutil, "which", lambda _name: None)
    result = mermaid.render("flowchart TD\n S1[x]", tmp_path / "out.svg")
    assert result.skipped is True
    assert result.ok is False
    # validate() must not block on a missing optional dependency.
    assert mermaid.validate("flowchart TD\n S1[x]") == (True, "")


def test_render_reports_parser_error_on_malformed_diagram(monkeypatch, tmp_path):
    # Simulate mmdc present but rejecting the diagram (non-zero exit + parser error).
    monkeypatch.setattr(mermaid.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(_cmd, **_kwargs):
        return types.SimpleNamespace(
            returncode=1, stdout="", stderr="Parse error on line 2: unexpected '('"
        )

    monkeypatch.setattr(mermaid.subprocess, "run", fake_run)
    result = mermaid.render("flowchart TD\n S1[bad (label)]", tmp_path / "out.svg")
    assert result.ok is False
    assert result.skipped is False
    assert "Parse error" in result.error


def test_render_succeeds_and_returns_image_path(monkeypatch, tmp_path):
    monkeypatch.setattr(mermaid.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(cmd, **_kwargs):
        out_path = Path(cmd[cmd.index("-o") + 1])
        out_path.write_text("<svg/>", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(mermaid.subprocess, "run", fake_run)
    out_svg = tmp_path / "out.svg"
    result = mermaid.render("flowchart TD\n S1[ok]", out_svg)
    assert result.ok is True
    assert result.image_path == out_svg
    assert out_svg.is_file()


# --- generate_diagram retry feedback -------------------------------------------------


def test_generate_diagram_injects_parser_feedback(monkeypatch):
    captured: dict[str, str] = {}

    def fake_complete(prompt, **_kwargs):
        captured["prompt"] = prompt
        return "flowchart TD\n    S1[Step 1]"

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
    feedback = pipeline._parser_feedback("Parse error on line 3")
    pipeline.generate_diagram(
        "## 6. Steps\n\n### Step 1 — Intake\n", parser_feedback=feedback
    )
    assert "RETRY" in captured["prompt"]
    assert "Parse error on line 3" in captured["prompt"]


def test_generate_diagram_first_pass_has_empty_feedback(monkeypatch):
    captured: dict[str, str] = {}

    def fake_complete(prompt, **_kwargs):
        captured["prompt"] = prompt
        return "flowchart TD\n    S1[Step 1]"

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
    pipeline.generate_diagram("## 6. Steps\n\n### Step 1 — Intake\n")
    # The placeholder is filled with an empty string on the first attempt.
    assert "{{PARSER_FEEDBACK}}" not in captured["prompt"]
    assert "RETRY" not in captured["prompt"]
