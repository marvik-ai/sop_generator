You are reconciling structured statements extracted from MULTIPLE source files before
they are assembled into an SOP. Each statement was extracted from a single file in
isolation, so cross-file disagreements have never been detected. Your one job is to find
them.

A **conflict** exists when two (or more) statements describe the **same subject** (the
same rule, threshold, value, field, list, or fact) but assert **different values**. The
classic case: one source says a duration-limit may be auto-extended by "5 days" and
another says "10 days" (or "ten days").

Hard rules:
- **Only report genuine same-subject value disagreements.** Do NOT report statements that
  merely cover different topics, complement each other, or restate the same value in
  different words.
- **Name both sides.** For every conflict, give each conflicting value AND the exact
  `source` filename it came from. Never collapse a conflict into a vague note.
- **Do not invent.** If two statements do not actually disagree, do not force a conflict.
  An empty array is a valid and common answer.
- Normalize obvious wording variants of the same number ("ten days" == "10 days") when
  deciding whether values differ — they are the SAME value, not a conflict.

For each conflict found, emit one object:

```json
{
  "subject": "Short description of what the sources disagree about.",
  "values": [
    {"value": "5 days", "source": "doc_02_rules_sheet_partial.md"},
    {"value": "10 days", "source": "transcript_04_restrictions_contradiction.md"}
  ],
  "suggested_gap_type": "AMBIGUITY"
}
```

`suggested_gap_type` is almost always `AMBIGUITY` (sources conflict).

=== EXTRACTED STATEMENTS (all files, each tagged with its source) ===
{{STATEMENTS_JSON}}
=== END EXTRACTED STATEMENTS ===

Output ONLY the JSON array of conflicts — no prose, no code fences. Output `[]` if there
are no genuine conflicts.
