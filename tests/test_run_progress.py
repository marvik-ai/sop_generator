"""Unit test for the sticky progress bar + ✅ markers in `pipeline.run()`: no API, no
mmdc — every LLM call and the diagram render are mocked, and the assertions only look at
the plain-text `capsys` capture (see CLAUDE.md and the plan this test implements: the
`\\r`/ANSI-clear control characters sit inertly between the real substrings, so `in` /
`.index()` checks are unaffected).
"""

from __future__ import annotations

import json

from sop_pipeline import mermaid, pipeline


_MINIMAL_SOP = (
    "## 1. Document control / metadata\n\n"
    "| Field | Value |\n|---|---|\n"
    "| SOP title | Test Process |\n"
    "| Last updated | 2026-01-01 |\n\n"
    "## 6. Step-by-step procedure\n\n"
    "### Step 1 — Intake\n\n"
    "- **Goal (plain language):** do the thing.\n"
    "- **Evaluation checkpoints:**\n"
    "  - Something happened.\n"
    "- **Open questions / gaps:** None\n\n"
    "## 10. Gaps Log\n\n"
    "| Gap ID | Type | Question | Status |\n|---|---|---|---|\n"
)

_DIAGRAM = "flowchart TD\n    S1[Step 1]\n    S1 --> S2\n    S2[Done]"


def _fake_complete_queue(monkeypatch, responses: list[str]) -> list[str]:
    """Pop canned responses in call order; the leftover queue proves the call count."""
    remaining = list(responses)

    def fake_complete(*_args, **_kwargs):
        assert remaining, "llm.complete was called more times than the queue expects"
        return remaining.pop(0)

    monkeypatch.setattr(pipeline.llm, "complete", fake_complete)
    return remaining


def test_run_marks_every_output_and_updates_the_bar_in_order(
    monkeypatch, tmp_path, capsys
):
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir()
    (inputs_dir / "a.md").write_text("doc a body", encoding="utf-8")
    (inputs_dir / "b.md").write_text("doc b body", encoding="utf-8")
    schema_guide_path = tmp_path / "schema_guide.md"
    schema_guide_path.write_text("schema guide placeholder", encoding="utf-8")
    out_dir = tmp_path / "out"

    responses = [
        json.dumps({"statements": []}),  # extract a.md
        json.dumps({"statements": []}),  # extract b.md
        json.dumps({"conflicts": []}),  # reconcile
        _MINIMAL_SOP,  # synthesize
        "Audit: no issues found.",  # gap_audit
        _MINIMAL_SOP,  # revise
        _DIAGRAM,  # generate_diagram
        "### Cross-cutting invariants\n\n(none)",  # synthesize_invariants
    ]
    remaining = _fake_complete_queue(monkeypatch, responses)

    svg_path = out_dir / "sop_flow_diagram.svg"
    monkeypatch.setattr(
        pipeline.mermaid,
        "render",
        lambda *_a, **_k: mermaid.RenderResult(ok=True, image_path=svg_path),
    )

    sop_path = pipeline.run(inputs_dir, out_dir, schema_guide_path)

    assert remaining == []  # every canned response was consumed, none left over
    out = capsys.readouterr().out

    # Phase headers appear, in order.
    idx = -1
    for header in (
        "STATEMENT EXTRACTION",
        "SOP DRAFT GENERATION",
        "SOP REFINEMENT",
        "ANNEX CREATION",
    ):
        next_idx = out.index(header)
        assert next_idx > idx
        idx = next_idx

    # Every intermediary/final output line ends with a checkmark.
    for line in (
        "extracted 0 statements from a.md ✅",
        "extracted 0 statements from b.md ✅",
        "SOP draft created ✅",
        "found 0 cross-file conflict(s). ✅",
        "audit report created at " + str(out_dir / "audit_report.md") + " ✅",
        "revised SOP created ✅",
        "flow diagram generated ✅",
        "invariants derived ✅",
        f"Done -> {sop_path} ✅",
    ):
        assert line in out

    # The progress checkpoints appear, in order: 20% and 40% (per-file, 2 docs), then the
    # phase checkpoints 70%, 90%, 100%.
    idx = -1
    for checkpoint in ("20%", "40%", "70%", "90%", "100%"):
        next_idx = out.index(checkpoint)
        assert next_idx > idx
        idx = next_idx
