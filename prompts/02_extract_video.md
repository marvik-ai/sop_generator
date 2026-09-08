You are extracting structured statements from ONE source recording for later assembly into an
SOP (a Standard Operating Procedure). Each extracted statement is one fact relevant to
*how a process works* — its scope, systems, glossary terms, triggers, decision rules,
actions, outcomes, thresholds, and end states. (Note: "extracted statement" here means a
unit of extracted information; it is unrelated to a CUSTOM_SYSTEM claim, which is the case the
SOP documents.)

## What you are given

- **{{FRAME_COUNT}} frames** sampled from the recording in chronological order, each
  preceded by a text marker with its timestamp, `[mm:ss]`.
- **The full timestamped transcript** of the narration, one `[mm:ss] text` line per
  segment.
- Total duration: **{{DURATION}}**.

Use the timestamps to align what was *said* with what was *on screen* at that moment. The
screen is the authority on names, labels and values — a spoken paraphrase never overrides
what a frame legibly shows.

Hard rules:
- **Extract only what this recording actually shows or says.** Do NOT infer, complete, or
  import outside knowledge, and do NOT complete a UI from familiarity with the system. If
  the recording is vague, capture it as vague.
- **Quote your evidence.** Every extracted statement must include a short verbatim
  `supporting_quote` — a transcript line for a spoken fact, or the literal on-screen text
  for a screen-only fact (e.g. `Applicability: Applicable`).
- **`supporting_media` is mandatory on every statement.** It is the timestamp range where
  you observed the fact, `mm:ss–mm:ss` (use `h:mm:ss` past an hour); repeat the same value
  on both sides for a single instant.
- **Not every fact has both channels — record it anyway.** A spoken statement with nothing
  legible on screen at that moment is still a statement: use the transcript timestamp for
  `supporting_media` and set `notes: "spoken only — nothing on screen"`. A fact only the
  screen shows, that narration never mentions, is recorded the same way in reverse, with
  `notes: "screen only — no spoken evidence"`. Never drop a fact for lacking the other
  channel.
- **Normalize garbled names** (ASR/spelling errors) to the intended term in `statement`,
  but keep the original wording in `supporting_quote`. Where screen and speech name the
  same object with different words, the on-screen spelling is authoritative for
  `statement`; keep the spoken word in `supporting_quote` and note the mismatch.
- **Flag conflicts and uncertainty.** If the narration hedges ("I think", "around", "check
  the spreadsheet") lower the confidence and note it. If screen and speech assert genuinely
  different facts — a different value, outcome, or order, not merely a different word for
  the same object — do not pick a side or average them: emit one statement for what was
  said and one for what was shown, each with its own quote and `supporting_media`, and set
  `conflicts_with` on each to name the other.
- **Capture forks as `decision` statements.** When the recording shows or says the process
  *splits into divergent paths* based on some value — e.g. "for a natural birth we do X,
  for a C-section we do Y" — record it with `target_section: "decision"`. In the
  `statement`, name the **discriminator** (the field/value that selects the path), the
  **branch values** it produces, and, only if the recording says so, **where the branches
  rejoin**. Do NOT invent branches, sub-steps, or a reconvergence point the recording never
  states; if it only gives a value difference (e.g. "8 weeks vs 6 weeks") that is an
  ordinary `step`/`business_rule`, not a `decision`.
- **Cover the whole recording.** The opening statement of purpose, the closing summary and
  every step or question in between each yield statements — do not compress the recording
  down to only its UI actions.

Map each extracted statement to the SOP section it belongs to. Use one of these
`target_section` values:
`scope`, `glossary`, `systems`, `process_overview`, `step`, `business_rule`,
`error_handling`, `end_state`, `gap`, `decision`.

Return a JSON array. Each element:

```json
{
  "target_section": "step",
  "statement": "In CUSTOM_SYSTEM, the adjudicator opens the Certification tab and reads the Applicability field.",
  "supporting_quote": "so now I jump into the certification tab",
  "supporting_media": "04:12–04:31",
  "confidence": "high | medium | low",
  "conflicts_with": "",
  "notes": "optional: hedging, ambiguity, 'screen only — no spoken evidence', 'spoken only — nothing on screen', a spoken-vs-on-screen name mismatch, or a value that may need confirmation"
}
```

=== SOURCE RECORDING: {{SOURCE_NAME}} ({{DURATION}}, {{FRAME_COUNT}} frames — {{FRAME_SAMPLING}}) ===

=== TRANSCRIPT ===
{{TRANSCRIPT}}
=== END TRANSCRIPT ===

The frames follow, each preceded by its `[mm:ss]` timestamp marker.

Output ONLY the JSON array — no prose, no code fences.
