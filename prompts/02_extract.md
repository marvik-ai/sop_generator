You are extracting structured statements from ONE source file for later assembly into an
SOP (a Standard Operating Procedure). Each extracted statement is one fact relevant to
*how a process works* — its scope, systems, glossary terms, triggers, decision rules,
actions, outcomes, thresholds, and end states. (Note: "extracted statement" here means a
unit of extracted information; it is unrelated to a CUSTOM_SYSTEM claim, which is the case the
SOP documents.)

Hard rules:
- **Extract only what this file actually says.** Do NOT infer, complete, or import
  outside knowledge. If the file is vague, capture it as vague.
- **Quote your evidence.** Every extracted statement must include a short verbatim
  `supporting_quote` from the source.
- **Normalize garbled names** (ASR/spelling errors) to the intended term in
  `statement`, but keep the original wording in `supporting_quote`.
- **Flag conflicts and uncertainty.** If the file hedges ("I think", "around", "check
  the spreadsheet") lower the confidence and note it.
- **Capture forks as `decision` statements.** When the file says the process *splits into
  divergent paths* based on some value — e.g. "for a natural birth we do X, for a
  C-section we do Y" — record it with `target_section: "decision"`. In the `statement`,
  name the **discriminator** (the field/value that selects the path), the **branch
  values** it produces, and, only if the file says so, **where the branches rejoin**. Do
  NOT invent branches, sub-steps, or a reconvergence point the source never states; if the
  source only gives a value difference (e.g. "8 weeks vs 6 weeks") that is an ordinary
  `step`/`business_rule`, not a `decision`.

Map each extracted statement to the SOP section it belongs to. Use one of these `target_section`
values:
`scope`, `glossary`, `systems`, `process_overview`, `step`, `business_rule`,
`error_handling`, `end_state`, `gap`, `decision`.

Return a JSON array. Each element:

```json
{
  "target_section": "step",
  "statement": "Concise, normalized statement of the fact.",
  "supporting_quote": "short verbatim snippet from the source",
  "confidence": "high | medium | low",
  "conflicts_with": "",
  "notes": "optional: hedging, ambiguity, or a value that may need confirmation"
}
```

=== SOURCE FILE: {{SOURCE_NAME}} ===
{{SOURCE_TEXT}}
=== END SOURCE FILE ===

Output ONLY the JSON array — no prose, no code fences.
