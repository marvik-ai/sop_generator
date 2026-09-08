# Pipeline overview

This pipeline reads a folder of meeting transcripts and documents
about a business process, and turns them into a Standard Operating Procedure (SOP) —
a structured markdown document describing exactly how that process works. If the
inputs don't say something clearly, the pipeline doesn't guess: it writes its best
attempt and clearly marks what's missing, so a human reviewer (a Business Analyst)
knows exactly what to check before approving the SOP.

There's also a side pipeline for testing: since the real client transcripts weren't
ready yet, we built a way to generate realistic *fake* transcripts and documents from
an SOP we already trust, then fed those fake inputs back through the real pipeline to
see how well it reconstructs the original — and whether it correctly notices what the
fake inputs deliberately left out.

## The three stages, at a glance

| Stage | Command | Description | Detail |
|---|---|---|---|
| 1 | `generate-mocks` | Manufacture realistic test inputs (and an answer key of what each one omits) | [generate-mocks.md](generate-mocks.md) |
| 2 | `run` | Turn a folder of inputs into a generated SOP | [run-pipeline.md](run-pipeline.md) |
| 3 | `evaluate` | Grade the generated SOP against the trusted SOP and the answer key | [evaluate.md](evaluate.md) |

## Why it's built this way

- **Flag, don't hallucinate.** The single rule that shapes every prompt in this
  pipeline. If information is missing, vague, or contradicted across sources, the
  output says so explicitly in a structured Gaps section — it never invents a
  plausible-sounding rule to fill the hole.
- **The pipeline logic lives in `prompts/`, not in Python.** The `.py` files under
  `src/sop_pipeline/` are thin glue: read files, call the model, save the result. If
  you want to change *what* the pipeline does, edit a prompt; the code rarely needs to
  change.

## Data flow (technical)

```
<user-supplied north-star SOP> ──┐
        (--north-star)           │ (background only, for realism)
                                  ▼
                    [1] generate-mocks ──► inputs/*.md, *.docx
                               │                  │
                               │                  ▼
                               │            fixtures/coverage_manifest.md
                               │            (ground truth: what each file omits)
                               │
inputs/* ──────────────────────────────────► [2] run
                                                   │
                                  ┌────────────────┼────────────────┐
                                  ▼                ▼                ▼
                          out/extraction.json  out/sop_generated.md  out/gaps_report.md
                                                   │
<user-supplied north-star SOP> ┐                   │
        (--north-star)         │                   │
fixtures/coverage_manifest.md ─┼──────────► [3] evaluate
                                │                   │
                                                     ▼
                                              out/evaluation.md
```

- **The north-star SOP** — the trusted, hand-authored SOP, supplied by the user via
  `--north-star` on both `generate-mocks` and `evaluate` (required, no default — it is
  **not tracked in this repo**, since committing it would leak the answer key). Used as
  background knowledge for stage 1 (to know what's realistic to put in a mock
  transcript) and as the answer key for stage 3. **Never** passed to the extraction or
  synthesis prompts in stage 2 — that would leak the answer into the thing being
  tested.
- **The schema guide** — the structural schema (11 required sections, the per-step
  block format, the typed gap categories), supplied by the user via `--schema-guide`
  on `run` (required, no default — it is **not tracked in this repo**). This **is**
  passed to stage 2's synthesis prompt, because it defines the shape of the output.
- **`fixtures/coverage_manifest.md`** — authored directly from the mock specs in
  `mocks.py` (not inferred from whatever the model wrote), so it's a reliable ground
  truth for grading gap detection in stage 3.

See each stage's own doc for the details.
