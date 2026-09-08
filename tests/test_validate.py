"""Unit tests for the deterministic gap-ID validator.

These run with no API key — they exercise pure string logic in
`sop_pipeline.validate.validate_gap_ids` and `validate_branches`.
"""

from __future__ import annotations

from sop_pipeline.validate import (
    _parse_mermaid,
    validate_branches,
    validate_diagram,
    validate_gap_ids,
    validate_systems_coverage,
)


# --- validate_systems_coverage ------------------------------------------------

_SOP_WITH_SECTION4 = (
    "## 4. Systems & data sources\n\n"
    "| System | What it is | Reads | Writes |\n|---|---|---|---|\n"
    "| CUSTOM_SYSTEM | Claims system of record | claim data | decisions |\n"
    "| Rules database | Stores business rules | rules | — |\n\n"
    "## 5. Process overview\n\nbody\n"
)


def test_systems_coverage_clean_when_all_present():
    statements = [
        {
            "target_section": "systems",
            "statement": "CUSTOM_SYSTEM is the claims system of record.",
            "source": "doc_01.md",
        },
        {
            "target_section": "systems",
            "statement": "The Rules database holds business rules.",
            "source": "doc_01.md",
        },
        {
            "target_section": "step",
            "statement": "Step 2 reads applicability.",
            "source": "t_01.md",
        },
    ]
    assert validate_systems_coverage(_SOP_WITH_SECTION4, statements) == []


def test_systems_coverage_flags_missing_system():
    statements = [
        {
            "target_section": "systems",
            "statement": "DocRepo is the document repository.",
            "source": "doc_03.md",
        },
    ]
    warnings = validate_systems_coverage(_SOP_WITH_SECTION4, statements)
    assert len(warnings) == 1
    assert "DocRepo" in warnings[0]
    assert "doc_03.md" in warnings[0]


def test_systems_coverage_ignores_non_systems_statements():
    statements = [
        {
            "target_section": "step",
            "statement": "A wholly unrelated step about widgets.",
            "source": "x.md",
        },
    ]
    assert validate_systems_coverage(_SOP_WITH_SECTION4, statements) == []


def test_systems_coverage_noop_without_section4():
    statements = [
        {
            "target_section": "systems",
            "statement": "DocRepo is the repository.",
            "source": "d.md",
        },
    ]
    assert (
        validate_systems_coverage("## 5. Process overview\n\nbody\n", statements) == []
    )


def _sop(section1: str, body: str, section10_rows: str) -> str:
    """Assemble a minimal SOP with the three sections the validator inspects."""
    return (
        "## 1. Document control / metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        f"{section1}\n\n"
        "## 6. Step-by-step procedure\n\n"
        f"{body}\n\n"
        "## 10. Open questions & gaps log\n\n"
        "| Gap ID | Type | Step | Question | Owner | Status |\n"
        "|---|---|---|---|---|---|\n"
        f"{section10_rows}\n\n"
        "## 11. Change log\n"
    )


def test_clean_sop_has_no_warnings():
    md = _sop(
        section1="| Author / owner | TBD |",
        body="Step 2 reads the Applicability field [GAP G-01].",
        section10_rows="| G-01 | OPAQUE-RULE | Step 2 | mapping? | | Open |",
    )
    assert validate_gap_ids(md) == []


def test_duplicate_row_id_is_flagged():
    md = _sop(
        section1="| Author / owner | TBD |",
        body="Step 2 [GAP G-01].",
        section10_rows=(
            "| G-01 | OPAQUE-RULE | Step 2 | mapping? | | Open |\n"
            "| G-01 | MISSING-DETAIL | Step 5 | screens? | | Open |"
        ),
    )
    warnings = validate_gap_ids(md)
    assert any("more than one Section 10 row" in w for w in warnings)


def test_inline_tag_without_row_is_flagged():
    md = _sop(
        section1="| Author / owner | TBD |",
        body="Step 2 [GAP G-01]. Step 5 [GAP G-99].",
        section10_rows="| G-01 | OPAQUE-RULE | Step 2 | mapping? | | Open |",
    )
    warnings = validate_gap_ids(md)
    assert any("Inline [GAP G-99] has no matching row" in w for w in warnings)


def test_orphan_row_never_referenced_is_flagged():
    md = _sop(
        section1="| Author / owner | TBD |",
        body="Step 2 [GAP G-01].",
        section10_rows=(
            "| G-01 | OPAQUE-RULE | Step 2 | mapping? | | Open |\n"
            "| G-02 | MISSING-DETAIL | Step 5 | screens? | | Open |"
        ),
    )
    warnings = validate_gap_ids(md)
    assert any("Section 10 row G-02 is never referenced" in w for w in warnings)


def test_bare_gap_reference_counts_as_referenced():
    # The per-step "Open questions / gaps" field uses the bare `G-xx` form, not a
    # bracketed tag — this must NOT be reported as an orphan row.
    md = _sop(
        section1="| Author / owner | TBD |",
        body="Step 3 eligibility check.\n- Open questions / gaps: G-03 (expected values).",
        section10_rows="| G-03 | MISSING-DETAIL | Step 3 | values? | | Open |",
    )
    assert validate_gap_ids(md) == []


def test_gap_tag_in_section1_metadata_is_flagged():
    md = _sop(
        section1="| Author / owner | [GAP G-01] |",
        body="Step 2 [GAP G-01].",
        section10_rows="| G-01 | OPAQUE-RULE | Step 2 | mapping? | | Open |",
    )
    warnings = validate_gap_ids(md)
    assert any("Section 1 metadata table" in w for w in warnings)


# --- validate_branches (true-bifurcation fork blocks) ---------------------------------

_FORK = (
    "### Step 5 — Delivery-type fork  [DECISION]\n\n"
    "- **Discriminator:** Delivery type (natural birth or C-section).\n"
    "- **Branches:**\n"
    "  - `Branch A — Natural birth`: IF natural THEN enter Step 5.A1.\n"
    "  - `Branch B — C-section`: IF C-section THEN enter Step 5.B1.\n"
    "- **Reconverges at:** Step 6 (Benefit-period decision).\n\n"
)
_BRANCH_A = (
    "### Step 5.A1 — Natural-birth evidence check\n\n"
    "- **Branch:** Branch A — Natural birth.\n"
    "- **Outcomes & routing:** continue to Step 6.\n\n"
)
_BRANCH_B = (
    "### Step 5.B1 — Surgical-recovery evidence check\n\n"
    "- **Branch:** Branch B — C-section.\n"
    "- **Outcomes & routing:** continue to Step 6.\n\n"
)
_RECONV = (
    "### Step 6 — Benefit-period decision\n\n"
    "- **Runs when (entry condition):** any branch completed — Step 5.A1 or Step 5.B1.\n\n"
)


def _fork_sop(body: str) -> str:
    return f"## 6. Step-by-step procedure\n\n{body}\n## 9. End-state catalog\n"


def test_no_fork_means_no_warnings():
    md = _fork_sop("### Step 1 — Intake\n\n- A plain linear step.\n\n")
    assert validate_branches(md) == []


def test_well_formed_fork_has_no_warnings():
    md = _fork_sop(_FORK + _BRANCH_A + _BRANCH_B + _RECONV)
    assert validate_branches(md) == []


def test_declared_branch_without_substep_is_flagged():
    # Branch B is declared in the fork block but has no Step 5.B* sub-step.
    md = _fork_sop(_FORK + _BRANCH_A + _RECONV)
    warnings = validate_branches(md)
    assert any("declares Branch B but no Step 5.B" in w for w in warnings)
    assert any("fewer than two branches" in w for w in warnings)


def test_substep_missing_branch_field_is_flagged():
    branch_a_no_field = (
        "### Step 5.A1 — Natural-birth evidence check\n\n"
        "- **Outcomes & routing:** continue to Step 6.\n\n"
    )
    md = _fork_sop(_FORK + branch_a_no_field + _BRANCH_B + _RECONV)
    warnings = validate_branches(md)
    assert any("Step 5.A1 has no 'Branch:' field" in w for w in warnings)


def test_missing_reconvergence_step_is_flagged():
    # Reconverges at Step 6, but no Step 6 heading exists.
    md = _fork_sop(_FORK + _BRANCH_A + _BRANCH_B)
    warnings = validate_branches(md)
    assert any(
        "reconverges at Step 6, but no such step heading exists" in w for w in warnings
    )


# --- validate_diagram (diagram <-> SOP consistency) ---------------------------------

_DIAGRAM_SOP = (
    "## 6. Step-by-step procedure\n\n"
    "### Step 1 — Intake\n\n"
    "- **Decision logic / rules:**\n"
    "  - `IF` a new claim `THEN` continue to step 2.\n"
    "- **Outcomes & routing:** → Step 2.\n\n"
    "### Step 2 — Applicability\n\n"
    "- **Decision logic / rules:**\n"
    "  - `IF` applicable `THEN` approve.\n"
    "  - `IF` not applicable `THEN` exclude.\n"
    "- **Outcomes & routing:** approve or exclude.\n\n"
    "## 9. End-state catalog\n\n"
    "| End state | When reached | What is recorded |\n"
    "|---|---|---|\n"
    "| Approved & closed | all pass | notes |\n"
    "| Excluded (logged) | a filter fails | notes |\n"
)

_CLEAN_DIAGRAM = (
    "flowchart TD\n"
    "    START([New claim]) --> S1[Step 1 — Intake]\n"
    "    S1 --> S2[Step 2 — Applicability]\n"
    "    S2 -->|applicable| DONE([Approved & closed])\n"
    "    S2 -->|not applicable| X[(Excluded — logged)]\n"
)


def test_parse_mermaid_extracts_nodes_and_edges():
    diagram = _parse_mermaid(_CLEAN_DIAGRAM)
    assert diagram.node_labels["S1"] == "Step 1 — Intake"
    assert diagram.node_labels["X"] == "Excluded — logged"  # cylinder shape stripped
    assert diagram.node_labels["DONE"] == "Approved & closed"  # stadium shape stripped
    assert ("S1", "S2") in diagram.edges
    assert ("S2", "DONE") in diagram.edges
    assert ("START", "S1") in diagram.edges


def test_clean_diagram_has_no_warnings():
    assert validate_diagram(_DIAGRAM_SOP, _CLEAN_DIAGRAM) == []


def test_diagram_missing_a_branch_is_flagged():
    # Drop the "not applicable" edge: Step 2 declares two IF/THEN branches but the node
    # is left with only one outgoing edge.
    missing = (
        "flowchart TD\n"
        "    START([New claim]) --> S1[Step 1 — Intake]\n"
        "    S1 --> S2[Step 2 — Applicability]\n"
        "    S2 -->|applicable| DONE([Approved & closed])\n"
        "    X[(Excluded — logged)]\n"
    )
    warnings = validate_diagram(_DIAGRAM_SOP, missing)
    assert any("Step 2 declares 2 IF/THEN branch" in w for w in warnings)


def test_invented_node_is_flagged():
    invented = _CLEAN_DIAGRAM + "    S2 --> S9[Step 9 — Ghost]\n"
    warnings = validate_diagram(_DIAGRAM_SOP, invented)
    assert any(
        "S9 has no matching Section 6 step (invented node)" in w for w in warnings
    )


def test_missing_step_node_is_flagged():
    # Diagram never defines or references S2.
    no_s2 = (
        "flowchart TD\n"
        "    START([New claim]) --> S1[Step 1 — Intake]\n"
        "    S1 --> DONE([Approved & closed])\n"
        "    X[(Excluded — logged)]\n"
    )
    warnings = validate_diagram(_DIAGRAM_SOP, no_s2)
    assert any("Step 2 has no matching node S2" in w for w in warnings)


def test_uncovered_end_state_is_flagged():
    sop_with_error_state = (
        _DIAGRAM_SOP + "| Technical error | runtime failure | error log |\n"
    )
    warnings = validate_diagram(sop_with_error_state, _CLEAN_DIAGRAM)
    assert any("Technical error" in w and "no terminal node" in w for w in warnings)
