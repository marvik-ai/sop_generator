## Overlay: revising an existing SOP (amends the rules above)

You are revising an existing SOP, supplied below (EXISTING SOP), using new extracted
statements gathered specifically to close its gaps. Output the **full revised SOP**,
covering Sections 1–11 as the schema guide defines them — not a diff, not a patch, not
a changelog.

This amends the base rule "build ONLY from the supplied extracted statements": the
existing SOP is now also an authorized source of fact. Carry its content over wherever the
new statements say nothing about it — do not re-derive, re-word, drop, or shorten sections
the new material does not touch.

How to merge:
- **Close resolved gaps.** For every gap in the existing SOP that the new statements
  answer: write the answer into the body (citing the new source file, as usual), remove its
  inline `[GAP G-xx]` tag, and remove its row from the gaps log section. After closing gaps,
  renumber all surviving gaps contiguously starting at `G-01` — including gaps that were not
  touched by this revision — so gap IDs stay dense with no skipped numbers.
- **Partial answers stay gaps.** If a new statement narrows a gap but doesn't fully answer
  it, keep it as a gap, re-worded to ask only about what is still missing.
- **Untouched gaps carry over unchanged** — same type, same question, same wording (only
  their ID may change due to renumbering).
- **A gap-tagged old value + a new statement supplying it → the new statement wins.** Close
  the gap; this is not an `AMBIGUITY`, it is the point of the revision.
- **A confident old value contradicted by new material → a new `AMBIGUITY` gap.** Name both
  values and both origins (`existing SOP` vs the new source's filename) — consistent with
  any matching entry in DETECTED CONFLICTS below.
- **New material may add content, not just fill holes.** New steps, rules, or end states
  the new statements introduce follow the base prompt's normal rules (inline `[GAP G-xx]`
  tags, typed gaps-log rows, IF/THEN decision logic, etc.) exactly as if this were a
  from-scratch synthesis.
- **Update the change log.** VERSION already reflects the bumped version number for this
  revision (the run computed it from the existing SOP's own `Version` field, incremented by
  0.1 — e.g. `0.1` becomes `0.2`). In Section 11, keep every existing row unchanged and append
  one new row for this revision using that VERSION value, RUN_DATE, and a brief description of
  what changed in this revision.
- **Never carry over the Annex/Appendix.** The EXISTING SOP
  below may already end with an appended "Annex 1: Mermaid diagram" and/or "Appendix
  A: Machine-readable evaluation checkpoint index" section. Do not carry it over.
- **When sourcing documents**: Cite the old SOP once, not its transitive
  sources.** Set this field to exactly: the existing SOP file
  ({{EXISTING_SOP_NAME}}) plus the new source file(s) used for this revision
  ({{NEW_INPUT_FILES}}).

=== REVISION SOURCE INFO ===
- EXISTING SOP FILE (being revised): {{EXISTING_SOP_NAME}}
- NEW SOURCE FILE(S) FOR THIS REVISION: {{NEW_INPUT_FILES}}
=== END REVISION SOURCE INFO ===

=== EXISTING SOP (the SOP being revised) ===
{{EXISTING_SOP}}
=== END EXISTING SOP ===
