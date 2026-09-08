You are extracting structured statements from ONE source recording for later assembly into an
SOP (a Standard Operating Procedure). Each extracted statement is one fact relevant to
*how a process works* — its scope, systems, glossary terms, triggers, decision rules,
actions, outcomes, thresholds, and end states. (Note: "extracted statement" here means a
unit of extracted information; it is unrelated to a CUSTOM_SYSTEM claim, which is the case the
SOP documents.)

**You are seeing one chunk of the recording at a time, in order.** This is chunk
**{{CHUNK_INDEX}} of {{CHUNK_COUNT}}**, covering **{{CHUNK_RANGE}}** of a {{DURATION}}
recording. You will never see the earlier chunks' frames or transcript again — the running
state below is your only memory of them. Your job is to **update** that state with what this
chunk adds, not to restate it.

## What you are given

- **The running state** so far: the action log, the last known UI/form state, and the items
  still open. (Empty on the first chunk.)
- **{{FRAME_COUNT}} frames** from THIS chunk in chronological order, each preceded by a text
  marker with its timestamp, `[mm:ss]`.
- **The transcript lines for THIS chunk**, one `[mm:ss] text` line per segment.

All timestamps you are given — frame markers and transcript lines alike — are **absolute**,
on the whole recording's clock. Every timestamp you emit must be absolute too: never
chunk-local, never restarted at `00:00`.

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
- **Cover the whole chunk.** Every step, question, aside and statement of purpose inside
  this chunk yields statements — do not compress the chunk down to only its UI actions.

## Sequential rules — what this chunk owes the next one

- **Emit only what is NEW in this chunk.** If a fact is already in the action log below,
  do not repeat it.
- **Do emit a correction or completion of an earlier entry** — a value that was illegible
  before and is now readable, a step whose outcome only appears now, a name the screen
  spells differently. Say in `notes` which logged entry it refines (quote a few words of it),
  and keep this chunk's own `supporting_media`.
- **Answer the open items when this chunk answers them.** List each one you closed in
  `resolved`, saying briefly what resolved it.
- **`ui_state`** must describe where the screen/form actually stands at the END of this
  chunk — the system, the screen/tab, the record in context, and any field values just
  entered or shown. Concrete enough that the next chunk can tell what changed. If the chunk
  ends mid-action, say so.
- **`open_questions`** is what is still unresolved after this chunk: carry forward what the
  log still leaves open, drop what you resolved, and add anything this chunk raised (a value
  the narrator promised to explain later, a screen that flashed by, a rule referenced but
  never stated).
- **Do not invent continuity.** If the recording jumps and you cannot tell how the screen
  got where it is, put that in `open_questions` — never fabricate the intervening steps to
  make the log read smoothly.
- **If this is the last chunk ({{CHUNK_INDEX}} of {{CHUNK_COUNT}})**, cover the closing
  summary and emit the process `end_state`. Leave `open_questions` populated with whatever
  the recording never answered rather than resolving it by assumption — those become the
  SOP's gaps.

Map each extracted statement to the SOP section it belongs to. Use one of these
`target_section` values:
`scope`, `glossary`, `systems`, `process_overview`, `step`, `business_rule`,
`error_handling`, `end_state`, `gap`, `decision`.

Return a JSON **object** (not a bare array):

```json
{
  "statements": [
    {
      "target_section": "step",
      "statement": "In CUSTOM_SYSTEM, the adjudicator opens the Certification tab and reads the Applicability field.",
      "supporting_quote": "so now I jump into the certification tab",
      "supporting_media": "04:12–04:31",
      "confidence": "high | medium | low",
      "conflicts_with": "",
      "notes": "optional: hedging, ambiguity, 'screen only — no spoken evidence', 'spoken only — nothing on screen', a spoken-vs-on-screen name mismatch, which logged entry this refines, or a value that may need confirmation"
    }
  ],
  "ui_state": "CUSTOM_SYSTEM, Certification tab of claim 12345; Applicability reads 'Applicable', nothing submitted yet.",
  "open_questions": ["The narrator said the threshold is 'in the spreadsheet' but never stated it."],
  "resolved": ["The pending 'which tab holds Applicability' item — the Certification tab, shown at 04:12."]
}
```

=== SOURCE RECORDING: {{SOURCE_NAME}} ({{DURATION}} total) ===
=== THIS CHUNK: {{CHUNK_INDEX}} of {{CHUNK_COUNT}}, {{CHUNK_RANGE}}, {{FRAME_COUNT}} frames — {{FRAME_SAMPLING}} ===

=== RUNNING STATE: ACTION LOG SO FAR ===
{{ACTION_LOG}}
=== END ACTION LOG ===

=== RUNNING STATE: LAST KNOWN UI / FORM STATE ===
{{UI_STATE}}
=== END UI STATE ===

=== RUNNING STATE: OPEN ITEMS ===
{{OPEN_QUESTIONS}}
=== END OPEN ITEMS ===

=== TRANSCRIPT (THIS CHUNK) ===
{{TRANSCRIPT}}
=== END TRANSCRIPT ===

The frames for this chunk follow, each preceded by its absolute `[mm:ss]` timestamp marker.

Output ONLY the JSON object — no prose, no code fences.
