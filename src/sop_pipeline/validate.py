"""Deterministic post-synthesis checks on the generated SOP.

No LLM calls — these are cheap structural guards that catch mechanical defects a model
sometimes introduces (e.g. reusing a gap ID for two different things, or tagging document
metadata as a gap). Warnings are advisory: they make a bad run visible without failing it.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


_INLINE_GAP = re.compile(r"\[GAP\s+(G-\d+)")
_ANY_GAP_ID = re.compile(r"\bG-\d+\b")
_SECTION17_HEADING = re.compile(r"^#+\s*17\.", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^#+\s+\d+\.", re.MULTILINE)
_SECTION1_HEADING = re.compile(r"^#+\s*1\.", re.MULTILINE)
_TABLE_GAP_ID = re.compile(r"^\|\s*(G-\d+)\s*\|", re.MULTILINE)

# Section 8 step headings. Captures the step id, which is either a plain number ("5") or a
# branch sub-step id ("5.A1" = fork at Step 5, Branch A, sub-step 1).
_STEP_HEADING = re.compile(
    r"^#{1,6}\s*Step\s+(\d+(?:\.[A-Za-z]\d+)?)\b[^\n]*$", re.MULTILINE
)
_SUBSTEP_ID = re.compile(r"^(\d+)\.([A-Za-z])\d+$")
_DECISION_MARK = re.compile(r"\[DECISION\]")
_DISCRIMINATOR_FIELD = re.compile(r"\*\*\s*Discriminator", re.IGNORECASE)
_RECONVERGES_FIELD = re.compile(r"\*\*\s*Reconverges at", re.IGNORECASE)
_BRANCH_FIELD = re.compile(r"\*\*\s*Branch\s*:?\s*\*\*", re.IGNORECASE)
_BRANCH_DECL = re.compile(r"\bBranch\s+([A-Za-z])\b")
_RECONV_TARGET = re.compile(r"Reconverges at[:\s*]*Step\s+(\d+)", re.IGNORECASE)
_INDEP_TERM = re.compile(r"terminate[s]? independently", re.IGNORECASE)


def _section(md: str, start: re.Pattern[str]) -> str:
    """Return the text from a numbered-section heading up to the next one (or EOF)."""
    start_match = start.search(md)
    if start_match is None:
        return ""
    rest = md[start_match.end() :]
    next_match = _NEXT_HEADING.search(rest)
    return rest[: next_match.start()] if next_match else rest


def validate_gap_ids(sop_md: str) -> list[str]:
    """Check inline `[GAP G-xx]` tags against the Section 17 gaps log.

    Returns a list of human-readable warnings (empty list == clean):
      - a gap ID declared on more than one Section 17 row (collision);
      - an inline `[GAP G-xx]` tag whose ID has no Section 17 row;
      - a Section 17 row never referenced anywhere in the body (orphan);
      - any `[GAP ...]` tag inside the Section 1 metadata table (document-admin misuse).

    A "reference" is any `G-xx` mention in the body outside the Section 17 table — both
    bracketed `[GAP G-xx]` tags and the bare `G-xx` form the per-step "Open questions /
    gaps" field uses count.
    """
    warnings: list[str] = []

    section17 = _section(sop_md, _SECTION17_HEADING)
    declared = _TABLE_GAP_ID.findall(section17)
    declared_set = set(declared)

    seen: set[str] = set()
    for gap_id in declared:
        if gap_id in seen:
            warnings.append(
                f"Gap ID {gap_id} is declared on more than one Section 17 row."
            )
        seen.add(gap_id)

    inline_ids = set(_INLINE_GAP.findall(sop_md))
    for gap_id in sorted(inline_ids - declared_set):
        warnings.append(f"Inline [GAP {gap_id}] has no matching row in Section 17.")

    body = sop_md.replace(section17, "")
    referenced = set(_ANY_GAP_ID.findall(body))
    for gap_id in sorted(declared_set - referenced):
        warnings.append(f"Section 17 row {gap_id} is never referenced in the body.")

    section1 = _section(sop_md, _SECTION1_HEADING)
    if _INLINE_GAP.search(section1):
        warnings.append(
            "A [GAP ...] tag appears in the Section 1 metadata table; document-admin "
            "fields should be 'TBD', not gaps."
        )

    return warnings


def validate_branches(sop_md: str) -> list[str]:
    """Check the integrity of any true-bifurcation fork blocks in Section 8.

    A fork is a step whose heading ends in `[DECISION]`; its branches run as sub-steps
    numbered `Step N.A1`, `Step N.B1`, … and may rejoin at a later "Reconverges at" step.
    Returns human-readable warnings (empty == clean / no forks present):
      - a fork missing its Discriminator or Reconverges-at field;
      - a fork with fewer than two branches, or a declared branch with no sub-step;
      - a branch sub-step missing its `Branch:` field, or pointing at a non-existent fork;
      - a "Reconverges at: Step M" target whose step heading does not exist;
      - a reconvergence step whose entry condition never references its feeder branches.
    """
    warnings: list[str] = []

    # Collect every step heading with its block text (heading start to next heading / EOF).
    matches = list(_STEP_HEADING.finditer(sop_md))
    if not matches:
        return warnings

    blocks: dict[str, str] = {}
    heading_lines: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sop_md)
        step_id = m.group(1)
        blocks[step_id] = sop_md[m.start() : end]
        heading_lines[step_id] = m.group(0)

    fork_ids = {
        sid for sid, line in heading_lines.items() if _DECISION_MARK.search(line)
    }

    # Map fork number -> set of branch letters that actually have sub-steps.
    substep_letters: dict[str, set[str]] = {}
    for sid in blocks:
        sub = _SUBSTEP_ID.match(sid)
        if sub:
            substep_letters.setdefault(sub.group(1), set()).add(sub.group(2).upper())

    for fork_id in sorted(
        fork_ids, key=lambda s: (int(s) if s.isdigit() else 1_000_000, s)
    ):
        block = blocks[fork_id]
        if not _DISCRIMINATOR_FIELD.search(block):
            warnings.append(f"Fork Step {fork_id} has no Discriminator field.")
        has_reconv_field = bool(_RECONVERGES_FIELD.search(block))
        if not has_reconv_field:
            warnings.append(f"Fork Step {fork_id} has no 'Reconverges at' field.")

        present = substep_letters.get(fork_id, set())
        if len(present) < 2:
            warnings.append(
                f"Fork Step {fork_id} has fewer than two branches with sub-steps "
                f"(found: {sorted(present) or 'none'})."
            )
        declared = {ltr.upper() for ltr in _BRANCH_DECL.findall(block)}
        for ltr in sorted(declared - present):
            warnings.append(
                f"Fork Step {fork_id} declares Branch {ltr} but no Step {fork_id}.{ltr}* "
                "sub-step exists."
            )

        target = _RECONV_TARGET.search(block)
        if target:
            reconv_id = target.group(1)
            if reconv_id not in blocks:
                warnings.append(
                    f"Fork Step {fork_id} reconverges at Step {reconv_id}, but no such "
                    "step heading exists."
                )
            elif not re.search(
                rf"Step\s+{fork_id}\.|branch", blocks[reconv_id], re.IGNORECASE
            ):
                warnings.append(
                    f"Reconvergence Step {reconv_id} never references the branches of "
                    f"fork Step {fork_id} in its entry condition."
                )
        elif has_reconv_field and not _INDEP_TERM.search(block):
            warnings.append(
                f"Fork Step {fork_id} neither names a reconvergence step nor states the "
                "branches terminate independently."
            )

    # Every branch sub-step must carry a Branch: field and point at a real fork.
    for sid, block in blocks.items():
        sub = _SUBSTEP_ID.match(sid)
        if not sub:
            continue
        if not _BRANCH_FIELD.search(block):
            warnings.append(f"Branch sub-step Step {sid} has no 'Branch:' field.")
        if sub.group(1) not in fork_ids:
            warnings.append(
                f"Branch sub-step Step {sid} has no parent fork Step {sub.group(1)} "
                "[DECISION] block."
            )

    return warnings


# --- Section 5 systems coverage (extraction -> SOP parity) ---------------------------

_SECTION5_HEADING = re.compile(r"^#+\s*5\.", re.MULTILINE)
# Generic function/SOP-boilerplate words that carry no system identity. Kept deliberately
# small so real system names (CUSTOM_SYSTEM, "rules database", "spreadsheet", …) survive the filter.
_SYSTEMS_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "of",
        "to",
        "from",
        "for",
        "and",
        "or",
        "in",
        "on",
        "at",
        "by",
        "with",
        "that",
        "this",
        "it",
        "its",
        "as",
        "used",
        "use",
        "uses",
        "when",
        "where",
        "into",
        "via",
        "system",
        "systems",
        "process",
        "data",
        "source",
        "sources",
        "store",
        "stores",
        "stored",
        "contain",
        "contains",
        "reads",
        "read",
        "writes",
        "write",
        "holds",
        "hold",
        "during",
    }
)


def _content_tokens(text: str) -> set[str]:
    """Identity-bearing tokens of `text` (alphanumerics >= 3 chars, minus stopwords)."""
    return {t for t in _words(text) if len(t) >= 3 and t not in _SYSTEMS_STOPWORDS}


def validate_systems_coverage(sop_md: str, statements: list[dict]) -> list[str]:
    """Advisory: flag any extracted `systems` statement absent from Section 5.

    Deterministic (no LLM) parity check between the extraction and the SOP's Systems & data
    sources table. For each statement tagged `target_section == "systems"`, warn when none
    of its identity-bearing tokens appear in Section 5 — i.e. the system it names was dropped
    from the table. Token-overlap (not exact match) keeps false positives low: a system that
    shows up under any wording still counts as covered. Returns warnings (empty == clean).
    """
    warnings: list[str] = []
    section5 = _section(sop_md, _SECTION5_HEADING)
    if not section5:
        return warnings
    section5_tokens = _content_tokens(section5)
    for stmt in statements:
        if stmt.get("target_section") != "systems":
            continue
        text = stmt.get("statement", "")
        tokens = _content_tokens(text)
        if tokens and not (tokens & section5_tokens):
            source = stmt.get("source", "?")
            warnings.append(
                f"Systems statement from {source} has no matching entry in Section 5: "
                f"{text!r}"
            )
    return warnings


# --- diagram <-> SOP consistency (Annex 1 Mermaid flowchart) -------------------------

# A Mermaid node definition: an id immediately followed by one of three shape wrappers.
# Order matters — the cylinder `[(...)]` and stadium `([...])` must be tried before the
# plain rectangle `[...]`. Labels are plain text by construction (see the diagram prompt's
# "Mermaid syntax safety" section), so the content classes never need to match brackets.
_NODE_DEF_RE = re.compile(
    r"\b(?P<id>[A-Za-z]\w*)"
    r"(?:"
    r"\(\[(?P<stadium>[^\]]*)\]\)"
    r"|\[\((?P<cylinder>[^)]*)\)\]"
    r"|\[(?P<rect>[^\]]*)\]"
    r")"
)
# A directed edge: `SRC ... --> DST` or the dotted `-.->`, with an optional `|label|`.
# One edge per line (the generator emits exactly one), so we match per line and take the
# first id as the source and the id after the operator as the target.
_EDGE_RE = re.compile(
    r"(?P<src>[A-Za-z]\w*)\b[^\n]*?(?:-\.->|-->)(?:\|[^|]*\|)?\s*(?P<dst>[A-Za-z]\w*)"
)
# Step nodes follow the `S<n>` / `S<n><letter><k>` convention from the diagram prompt.
_STEP_NODE_RE = re.compile(r"^S\d+(?:[A-Za-z]\d+)?$")
_THEN_RE = re.compile(r"\bTHEN\b", re.IGNORECASE)
_SECTION15_HEADING = re.compile(r"^#+\s*15\.", re.MULTILINE)
_TABLE_FIRST_CELL_RE = re.compile(r"^\|\s*([^|]+?)\s*\|")
_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class _Diagram:
    """Parsed Mermaid source: just enough structure for the consistency checks."""

    node_labels: dict[str, str] = field(default_factory=dict)
    node_def_counts: Counter = field(default_factory=Counter)
    node_ids: set[str] = field(default_factory=set)  # defined or referenced anywhere
    edges: list[tuple[str, str]] = field(default_factory=list)  # (src, dst)


def _parse_mermaid(mmd_source: str) -> _Diagram:
    """Extract node definitions and directed edges from Mermaid flowchart source."""
    diagram = _Diagram()
    for match in _NODE_DEF_RE.finditer(mmd_source):
        node_id = match.group("id")
        label = match.group("stadium") or match.group("cylinder") or match.group("rect")
        diagram.node_labels[node_id] = label.strip()
        diagram.node_def_counts[node_id] += 1
        diagram.node_ids.add(node_id)
    for line in mmd_source.splitlines():
        edge = _EDGE_RE.search(line)
        if edge:
            src, dst = edge.group("src"), edge.group("dst")
            diagram.edges.append((src, dst))
            diagram.node_ids.update((src, dst))
    return diagram


def _node_id_for_step(step_id: str) -> str:
    """Map a Section 8 step id to its diagram node id ('5.A1' -> 'S5A1', '3' -> 'S3')."""
    return "S" + step_id.replace(".", "")


def _step_blocks(sop_md: str) -> dict[str, str]:
    """Section 8 step id -> its block text (heading to the next step heading / EOF)."""
    matches = list(_STEP_HEADING.finditer(sop_md))
    blocks: dict[str, str] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sop_md)
        blocks[m.group(1)] = sop_md[m.start() : end]
    return blocks


def _end_states(sop_md: str) -> list[str]:
    """First-column labels of the Section 15 End-state catalog table."""
    section15 = _section(sop_md, _SECTION15_HEADING)
    states: list[str] = []
    for line in section15.splitlines():
        cell = _TABLE_FIRST_CELL_RE.match(line)
        if not cell:
            continue
        label = cell.group(1).strip()
        # Skip the header row and the |---|---| separator.
        if not label or set(label) <= {"-", " ", ":"} or label.lower() == "end state":
            continue
        states.append(label)
    return states


def _words(text: str) -> set[str]:
    """Lower-cased alphanumeric tokens of `text` (for fuzzy label matching)."""
    return set(_WORD_RE.findall(text.lower()))


def validate_diagram(sop_md: str, mmd_source: str) -> list[str]:
    """Check the generated Mermaid diagram mirrors the SOP it was built from.

    Deterministic (no LLM) structural parity between Annex 1 and the SOP body. Returns
    human-readable warnings (empty == clean):
      - node/step parity: every Section 8 step has exactly one node; no node is invented;
      - branch/edge parity: a step's node has at least as many outgoing edges as the step
        declares IF/THEN branches (a heuristic upper bound — multiple IF/THEN clauses may
        legitimately converge to one target, so this is advisory and only flags a *deficit*);
      - end-state coverage: every Section 15 end state appears as a terminal node.

    Not covered (tracked separately, see the ticket): visualising `[GAP G-xx]` routing tags,
    and run-to-run id/label drift from the LLM generator.
    """
    warnings: list[str] = []
    diagram = _parse_mermaid(mmd_source)
    out_degree = Counter(src for src, _ in diagram.edges)
    blocks = _step_blocks(sop_md)

    # --- node/step parity ---
    expected = {_node_id_for_step(step_id): step_id for step_id in blocks}
    for node_id, step_id in sorted(expected.items()):
        if node_id not in diagram.node_ids:
            warnings.append(
                f"Section 8 Step {step_id} has no matching node {node_id} in the diagram."
            )
        elif diagram.node_def_counts.get(node_id, 0) > 1:
            warnings.append(
                f"Diagram node {node_id} (Step {step_id}) is defined more than once."
            )
    step_nodes = {nid for nid in diagram.node_ids if _STEP_NODE_RE.match(nid)}
    for node_id in sorted(step_nodes - set(expected)):
        warnings.append(
            f"Diagram node {node_id} has no matching Section 8 step (invented node)."
        )

    # --- branch/edge parity (advisory heuristic) ---
    for step_id, block in blocks.items():
        node_id = _node_id_for_step(step_id)
        if node_id not in diagram.node_ids:
            continue  # already reported as a missing node above
        actual = out_degree.get(node_id, 0)
        branches = len(_THEN_RE.findall(block))
        if actual == 0:
            warnings.append(
                f"Step {step_id} node {node_id} has no outgoing edge in the diagram."
            )
        elif branches > 1 and actual < branches:
            warnings.append(
                f"Step {step_id} declares {branches} IF/THEN branch(es) but node "
                f"{node_id} has only {actual} outgoing edge(s); a routing branch may be "
                "missing from the diagram."
            )

    # --- end-state coverage ---
    terminal_word_sets = [
        _words(label)
        for nid, label in diagram.node_labels.items()
        if out_degree.get(nid, 0) == 0
    ]
    for end_state in _end_states(sop_md):
        words = _words(end_state)
        if words and not any(words <= terminal for terminal in terminal_word_sets):
            warnings.append(
                f"End state '{end_state}' from Section 15 has no terminal node in the "
                "diagram."
            )

    return warnings
