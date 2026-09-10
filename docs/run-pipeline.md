# Stage 2 — `run`

```bash
uv run sop-pipeline run --inputs inputs/
```

## Plain language

This is the actual product: point it at a folder of transcripts and documents, and it
writes a structured SOP. Internally it works in four steps, the same way a human
analyst would:

1. **Read every file and pull out the facts** — who said what, where it came from.
2. **Write the SOP** using only those facts, following a fixed structure. Anywhere
   information is missing, unclear, or two sources disagree, it says so explicitly
   instead of guessing.
3. **Double-check itself** — re-read the SOP it just wrote against the original files
   and flag anything that looks made up, or any hole it should have flagged but didn't.
4. **Draw the process** — turn the finished step-by-step into a Mermaid flow diagram,
   one box per step with a labeled arrow for each decision branch and exit.

## What it produces (in `out/`)

| File | What it is |
|---|---|
| `extraction.json` | Every fact pulled from every input file, before synthesis. Useful for debugging — if the SOP is missing something, check here first: was the fact even extracted? |
| `sop_generated.md` | The SOP itself — the final deliverable. Ends with `## Annex 1: Mermaid diagram`, the flow diagram of the procedure. |
| `gaps_report.md` | A self-audit: hallucinations found, gaps that should have been flagged but weren't, and a structural pass/fail. |
| `sop_flow_diagram.mmd` | The Mermaid flow diagram on its own, for rendering or embedding elsewhere (identical to the SOP's Annex 1). |
| `sop_flow_diagram.svg` | The flow diagram rendered to an image (via the Mermaid CLI), linked from Annex 1 so Word/PDF readers see a picture, not source. Only written when `mmdc` is available. |

## The four steps in detail (technical)

### 2a. Ingest (`ingest.py`)

Reads every `.docx`, `.md`, `.txt`, `.mp4` file in the inputs folder (alphabetically, for
determinism) into a list of `SourceDoc(name, text, path, members)`. This step is pure IO: a
`.mp4` records only its path with empty text (no decoding, no API calls — see 2b-bis), and a
**subdirectory** records only its files as `members` with empty text of its own (see
2b-ter). Each chunk of text keeps its source filename attached — this matters because the SOP schema requires stating the
source of every input, and the gap-audit step needs the original text to check
against.

### 2b. Extract (`prompts/02_extract.md`, run once per file)

For each source file, sends its full text to the model (`SOP_EXTRACT_MODEL`, default the
cheaper `gpt-4o-mini`, since this step runs once per file) with instructions to
pull out every fact relevant to the process — scope, systems, glossary terms,
triggers, decision rules, thresholds, end states — as a JSON array of extracted
statements (units of extracted information, not to be confused with CUSTOM_SYSTEM claims):

```json
{
  "target_section": "step",
  "statement": "Normalized version of the fact",
  "supporting_quote": "verbatim snippet from the source",
  "confidence": "high | medium | low",
  "conflicts_with": "",
  "notes": "hedging, ambiguity, etc."
}
```

Key behaviors baked into the prompt:
- **Extract only what the file says** — no inferring or filling gaps with outside
  knowledge at this stage. That happens explicitly and visibly in the next step.
- **Quote the evidence** for every extracted statement (`supporting_quote`), so later
  steps (and a human reviewer) can trace any statement back to its source.
- **Normalize garbled names** in `statement` (e.g. ASR mangling "Finios" → "CUSTOM_SYSTEM")
  but keep the original wording in the quote.
- **Lower confidence on hedged language** ("I think", "around", "check the tip
  sheet").

Each extracted statement is then tagged with its source filename in
`pipeline.extract()`. Extracted statements from every file accumulate into one combined
list — this is what makes cross-file synthesis possible: a fact that only appears in one
file still makes it into the pool, and the next step can also see when two files'
extracted statements disagree.

The model's response isn't always clean JSON (it might wrap it in a code fence or add
a sentence before/after), so `llm.parse_json_array()` tolerantly extracts the
JSON array regardless of minor formatting noise, and returns an empty list if nothing
parseable is found (rather than crashing the whole run on one bad file).

### 2b-bis. Video extraction (the video module, run once per `.mp4`)

A `.mp4` input — typically a screen recording of a BSA walking through CUSTOM_SYSTEM — takes a
separate branch inside the same extract step. `ingest.load_corpus()` does **no** decoding: a
video yields `SourceDoc(name, text="", path=…)`, and all the work happens in
`pipeline._extract_video()`.

**One function: `video.extract(path)`.** `src/sop_pipeline/video/` owns the whole recording →
statements path, and *how* it does it is a **strategy**: `config.yaml`'s `strategy` key
picks one, its knobs come from that same file (overridable via a custom config file
pointed to by the `SOP_VIDEO_CONFIG` env var), and **[`src/sop_pipeline/video/README.md`](../src/sop_pipeline/video/README.md)
is the reference** for what the strategies are, what each costs, and when each wins.
Whichever runs, the shape of the work is the same: sample frames with `ffmpeg`
(`video/media.py`), transcribe the audio with `whisper-1` onto the recording's absolute clock
(`video/transcribe.py`), then send frames + transcript to `SOP_VIDEO_MODEL` with the
strategy's prompt, constrained by a Structured Outputs schema from `video/schema.py`.

Everything `pipeline.py` knows about that is three functions — `video.extract()`,
`video.cache_key()` and `video.prompt_name()` — so the choice of strategy is invisible to the
rest of the pipeline and to every artifact it writes.

The ffmpeg binary comes from the `imageio-ffmpeg` dependency, so `uv sync` alone is
enough — no `sudo`, no system ffmpeg install. If the wheel has no binary for the current
platform, extraction raises an error naming the remedy rather than silently producing
nothing.

**Same artifact as every other source.** The video branch produces the identical
statement-list artifact (`out/extraction_cache/<name>.json`, folded into
`out/extraction.json` with its `source` tag), so `reconcile` → `synthesize` → `gap_audit` →
`diagram` are completely untouched. There is no intermediate prose document: the video is
extracted **directly to facts**.

**The one schema addition: `supporting_media`.** Video statements carry the same object as
the text path plus a mandatory `supporting_media` — the timestamp range where the fact was
observed (`mm:ss–mm:ss`, or `h:mm:ss` past an hour; a single instant repeats the value):

```json
{
  "target_section": "step",
  "statement": "In CUSTOM_SYSTEM, the adjudicator opens the Certification tab and reads the Applicability field.",
  "supporting_quote": "so now I jump into the certification tab",
  "supporting_media": "04:12–04:31",
  "confidence": "high",
  "conflicts_with": "",
  "notes": ""
}
```

Every existing consumer treats statements as opaque dicts, so the extra key flows through
untouched; `prompts/03_synthesize_sop.md` uses it to cite the recording and timestamp in a
step block.

**Two evidence channels.** `supporting_quote` is a verbatim transcript line when the fact was
*spoken*. When a fact is only *visible* — a field value on screen that nobody says aloud —
the quote is the literal on-screen text as rendered (e.g. `Applicability: Applicable`) and
`notes` records `screen only — no spoken evidence`. Unreadable UI (too small, blurred, cut
off, scrolled past) becomes a `target_section: "gap"` statement, never a guessed field name:
"flag, don't hallucinate" holds at the video layer too.

**No silent truncation.** How a long recording is kept inside the context window is exactly
what the strategies differ on — thinning the frames uniformly versus chunking the recording
and carrying a running state — and neither drops the **end** of the procedure, the worst
possible loss for an SOP. The prompt always states how coarse the samples are, so the model
knows what it is and is not being shown. See the [video README](../src/sop_pipeline/video/README.md)
for the trade-off.

**The gap-audit corpus for a video.** `gap_audit` is fed the *raw* corpus
(`combined_corpus(docs)`), and `doc.text` is empty for a video after ingest. So
`_extract_video()` sets `doc.text` from the statements themselves — `pipeline._video_corpus()`
renders one `- [supporting_media] supporting_quote` line per statement. Those verbatim quotes
*are* the recording's source text (a spoken line for a narrated fact, the literal rendered
string for a screen-only one), and without them the auditor would flag every video-derived
SOP fact as an unsupported hallucination. That text is stored in the cache entry as
`source_text` and restored on a cache hit, so cached and uncached runs audit identically.

**Extraction is cache-first.** Because ingest does no decoding, a cached run touches neither
ffmpeg nor the OpenAI API for a video. The cache key is `video.cache_key()` (the selected
strategy's name plus every one of its knobs) + the strategy's prompt text + the video file's
SHA-256, so editing that prompt, changing a knob, or switching `strategy` in `config.yaml`
re-extracts automatically — exactly like editing `02_extract.md` does today.
`run --force-extract` forces it; `run` gains no video-specific flags.

### 2b-ter. Folder extraction (`prompts/02_extract_folder.md`, run once per subdirectory)

A subdirectory of the inputs folder is a **related document set**: several records of the
same session — typically a screen recording, a transcript of it, and notes about it.
A subdirectory takes a third branch inside the extract step and yields **one** statement
list for the whole folder.

`pipeline._extract_folder()` does it in one order that matters:

1. **Member recordings first.** Each `.mp4` in the folder goes through
   `_extract_video()` (its own cache entry, its own strategy — nothing about 2b-bis changes),
   producing statements with their `supporting_media` timestamps.
2. **Merge the text.** `doc.text` becomes the members' labeled texts concatenated — including
   each recording's `_video_corpus()` evidence lines, which is what makes the folder's cache
   key sensitive to the recording and gives `gap_audit` its source text.
3. **One fused call.** The folder's text documents *and* the recordings' statements (as JSON,
   timestamps intact) go to `02_extract_folder.md` in a single call. A folder holding nothing
   but recordings skips this call and returns their statements as they are — with no text to
   fuse them with, the call could only re-emit what it was handed.

The prompt's job is the part the per-file map cannot do:

- **Consolidate agreement** — a fact two or three members state becomes one statement, in the
  most specific wording available.
- **Never pick a winner** — when members give different *values* for the same thing, it emits
  one statement per version, each with its own `source` and quote, cross-referenced through
  `conflicts_with`. Resolving the disagreement is not its job; `reconcile` and the gap audit
  flag it downstream. "Flag, don't hallucinate" applied inside a document set. This is the
  rule the fusion breaks first: left to itself the model folds the weaker-sounding version
  ("I think it's ten days") into the winner's `conflicts_with` note, where `reconcile` — which
  compares statements, not notes — can no longer see it, and the SOP loses a contradiction the
  per-file map would have kept. Hence the prompt's closing self-check, and
  `integration_tests/test_extract.py::test_extract_from_a_folder_whose_documents_disagree`.
- **The recording is the authority on names, labels and values** when a transcript garbles a
  term that is legible on screen — that is normalization, not a conflict.

Two schema additions, on `FolderStatement` only (`schema.py`) — the flat-file `DocStatement`
is untouched, so no existing extraction is invalidated:

- **`supporting_media`** — copied verbatim from the recording statement a fact came from,
  `""` for a text-only fact. Same key the video path already produces, so
  `03_synthesize_sop.md` cites the recording and timestamp exactly as before.
- **`source`** — the model names the member file its quote came from, rather than Python
  tagging the whole batch. Member names are folder-qualified (`session_a/notes.md`), so SOP
  citations stay file-level and `reconcile` can still name both sides of a conflict. A name
  that is not a real member is replaced with the folder's own name, so `source` is never
  invented.

**The gap-audit corpus for a folder.** `combined_corpus(docs)` wraps the folder's already-
labeled members, so the auditor sees nested source blocks: the outer label says these files
are one session, the inner ones preserve which file a quote came from.

### 2c. Synthesize (`prompts/03_synthesize_sop.md`, run once on all extracted statements)

This is where the **"flag, don't hallucinate"** rule is enforced. The prompt gets:
- The user-supplied schema guide (`--schema-guide`) — the schema to follow exactly (11
  sections, the per-step block format, the typed gap categories).
- The full JSON list of extracted statements from every input file.

It does **not** get the north-star SOP — only the statements actually extracted from the
actual inputs. The model is instructed to:
- Build the SOP only from the supplied extracted statements, citing the source file for
  every input.
- Consolidate extracted statements that agree across sources.
- When extracted statements **conflict**, present the conflict and raise it as a typed gap
  rather than picking a side.
- When an extracted statement is hedged/low-confidence, use it but flag it.
- When the schema expects something the extracted statements never cover at all, write what's known,
  insert an inline `[GAP G-xx]` tag, and add a row to Section 12 — never invent the
  missing piece.
- Use explicit `IF <condition> THEN <outcome>` for every decision, covering the
  "otherwise" case.
- Never use code symbols, function names, or tool names — only business language
  (system, screen, field, value, action).

Runs on `SOP_SYNTH_MODEL` (default `gpt-4o`) since this is the highest-stakes
single call in the pipeline.

### 2d. Gap audit (`prompts/04_gap_audit.md`)

A separate, independent pass: feeds the generated SOP back to the model alongside the
**raw original corpus** (not the extracted statements — the actual source text), and asks
it to QA the synthesis step's work:

1. **Hallucinations** — any statement, rule, value, or field in the SOP not supported
   by any source file.
2. **Missing gaps** — anything the SOP states as settled fact that the corpus only
   hints at, hedges on, contradicts, or never mentions, but which wasn't tagged with a
   `[GAP G-xx]`.
3. **Gap quality** — are the gaps that *were* raised concrete, correctly typed, and
   actionable as questions for a reviewer?
4. **Structural checks** — all 11 sections present, every step uses the block schema,
   every decision is IF/THEN, no code/function/tool names leaked in.

Outputs a markdown report ending in a `PASS` / `PASS WITH NOTES` / `FAIL` verdict.
Runs on `SOP_JUDGE_MODEL` (default `gpt-4o`).

### 2e. Diagram (`prompts/06_generate_diagram.md`)

A final pass that turns the finished SOP into a Mermaid `flowchart TD`. It runs **after**
the gap audit on purpose — the audit checks only the SOP body, so the diagram text never
trips the hallucination check.

The prompt gets the synthesized SOP and is instructed to **mirror, not invent**: one node
per Section 7 step (`S1[Step 1 — …]`, in order), a labeled edge for every branch in each
step's *Outcomes & routing* / *Stop / exit conditions* (including the "otherwise"/stop
branch), and distinct terminal nodes for the end states from Sections 5 and 9 (reusing one
node id when several steps route to the same outcome). It carries the north-star diagram as a
format example so node shapes and edge-label style stay consistent.

`pipeline.generate_diagram()` strips a stray ```` ```mermaid ```` fence if the model adds one
(`_strip_code_fence`), then `run()` wraps the result in a fenced block, appends it to
`sop_generated.md` as `## Annex 1: Mermaid diagram`, and also writes it standalone to
`out/sop_flow_diagram.mmd`. Runs on `SOP_SYNTH_MODEL` (default `gpt-4o`) at temperature 0.

#### Diagram guards (`pipeline.build_diagram()`, `mermaid.py`, `validate.validate_diagram()`)

The raw generation is unguarded, so `build_diagram()` wraps it with three checks:

1. **Parse validation + render (`mermaid.py`).** The diagram is rendered with the Mermaid
   CLI (`mmdc`, found on `PATH` or fetched via `npx @mermaid-js/mermaid-cli`). Because `mmdc`
   parses before it renders, a clean render *is* the parse check and simultaneously writes
   `out/sop_flow_diagram.svg`. If it fails to parse, the diagram is **regenerated once** with
   the parser error fed back into the prompt (the `{{PARSER_FEEDBACK}}` retry block); if it
   still fails, a loud warning is surfaced in the run output — no silent broken diagram. When
   `mmdc` is not installed, the parse/render guard is **skipped with a warning** (the pipeline
   stays runnable without Node); the `.mmd` and SOP are still written.
2. **Consistency check (`validate.validate_diagram()`).** A deterministic (no-LLM) parity
   check between Annex 1 and the SOP body: every Section 7 step appears as exactly one node
   (and no node is invented), each step's node has at least as many outgoing edges as the step
   declares IF/THEN branches (an advisory heuristic — it flags a deficit only), and every
   Section 11 end state appears as a terminal node. Mismatches print as warnings.

Not covered (tracked separately): visualising `[GAP G-xx]` routing tags in the diagram, and
run-to-run id/label drift from the LLM generator.

## Revision mode (`--sop <path>`)

The client loop, once an SOP already exists: its `[GAP G-xx]` rows were taken to the
business, the answers came back as new transcripts/documents, and those need to fold
back into the SOP rather than forcing a from-scratch regeneration that loses everything
already agreed.

`--sop <path>` switches `run` onto this route. Extraction is unchanged — the new raw
material goes through the normal per-file/video/folder map step. The existing SOP joins
the pipeline at exactly two points:

- **Reconcile** (`prompts/07_reconcile.md` + the `07b_reconcile_with_sop.md` overlay,
  appended only when `--sop` is given): the SOP's confidently-stated content is compared
  against the new extracted statements like any other source. A same-subject value
  disagreement is a conflict; a value the SOP itself already flagged as a gap is *not* —
  a new statement supplying it is a resolution.
- **Synthesize** (`prompts/03_synthesize_sop.md` + the `03b_revise_existing_sop.md`
  overlay): the model outputs the full revised SOP, not a diff. Resolved gaps lose their
  inline `[GAP G-xx]` tag and Section 12 row (surviving gaps renumber contiguously from
  `G-01`); untouched sections and unresolved gaps carry over unchanged; a confident
  contradiction becomes a new `AMBIGUITY` gap naming both the SOP and the new source.

The gap-audit corpus (`gap_audit` checks the synthesized SOP against the raw sources) is
also extended with the old SOP's content — otherwise everything carried over from it
reads as an unsupported hallucination.

With no `--sop`, both overlays are skipped and the two prompts reach the model exactly as
in from-scratch mode — the revision route adds nothing to the default path.

## Where to make changes

- **Change what facts get extracted, or how aggressively:** edit
  `prompts/02_extract.md`.
- **Change how a folder of related documents is fused** (what counts as agreement, how
  intra-folder conflicts are preserved, attribution): edit
  `prompts/02_extract_folder.md`. This leaves the flat-file extraction cache valid. The two
  extract prompts share their rules — the `target_section` list, the `decision`-fork rule,
  the quoting and hedging rules — deliberately copied rather than factored out, so each reads
  as one whole instruction; a change to a shared rule belongs in both files.
- **Change what gets extracted from a screen recording** (evidence channels, when
  unreadable UI becomes a gap, `supporting_media` conventions): edit the prompt of the
  selected video strategy — `video.prompt_name()` names it, see
  [`src/sop_pipeline/video/README.md`](../src/sop_pipeline/video/README.md). Editing it
  invalidates the video extraction cache, so the next run re-extracts.
- **Change the SOP's structure or the hallucination rules:** edit
  `prompts/03_synthesize_sop.md`. The actual section structure itself lives in the
  user-supplied schema guide (`--schema-guide`), not in this prompt — that's the
  source of truth for the schema.
- **Change what the self-audit checks for:** edit `prompts/04_gap_audit.md`.
- **Change the flow diagram's shape or conventions:** edit `prompts/06_generate_diagram.md`.
- **Swap models:** set `SOP_EXTRACT_MODEL` / `SOP_SYNTH_MODEL` / `SOP_JUDGE_MODEL` /
  `SOP_VIDEO_MODEL` / `SOP_TRANSCRIBE_MODEL` in `.env`.
- **Change how a recording is turned into facts:** set `strategy`, or tune the selected
  strategy's knobs, in `src/sop_pipeline/video/config.yaml` — or, to avoid editing the
  checked-in defaults, in a custom YAML file anywhere, pointed to by the `SOP_VIDEO_CONFIG`
  env var (see [`src/sop_pipeline/video/README.md`](../src/sop_pipeline/video/README.md)).
  Both the strategy and its knobs are hashed into the video extraction cache key, so the
  next run re-extracts.
- **Add a new way of reading recordings:** add a strategy module under
  `src/sop_pipeline/video/` — the contract and the checklist are in that folder's README. No
  change outside it is needed.
