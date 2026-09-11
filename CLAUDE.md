# CLAUDE.md — sop_pipeline

## What this is
Self-contained pipeline: folder of inputs (transcripts + docs) → structured SOP in
markdown, flagging gaps instead of hallucinating. **Does not import from the rest of
the repo.** All paths below are relative to `sop_pipeline/`.

## Critical rules
- **Flag, don't hallucinate.** If a fact is missing/uncertain/contradictory, write the
  best-known version + an inline `[GAP G-xx]` + a typed row in SOP Section 12. Never
  invent a rule to fill a hole.
- **The pipeline logic lives in `prompts/`, not in Python.** `src/sop_pipeline/*.py` is
  thin glue (CLI, file IO, OpenAI calls, orchestration). Change behavior by editing
  prompts first.
- **The north star is for grading only, and is not tracked in the repo.** It is a
  user-supplied file passed via `--north-star <path>` to `generate-mocks` and
  `evaluate` (both require the flag — no default path). It must **never** be passed to
  the extract/synthesize prompts — that would leak the answer. Only `evaluate` reads
  it (`generate-mocks` uses it only as background realism context).
- **The schema guide drives output shape.** It is a user-supplied file passed via
  `--schema-guide <path>` to `run` (required — no default path, not tracked in the
  repo). It defines the 15 required sections + per-step block + typed Gaps Log; the
  synthesize prompt must follow it exactly.
- **Two modes for `run`.** With no `--sop`, `run` writes a brand-new SOP from the inputs.
  With `--sop <path>`, it revises that existing SOP instead: the new inputs' extracted
  statements fill its gaps while untouched content and
  unresolved gaps carry over unchanged.
- **`--sop-name` scopes a run to one SOP.** A folder of inputs can mix material from
  several distinct processes; `--sop-name "<name>"` runs a filtering step (after extract,
  before reconcile) that keeps only statements relevant to that named SOP. Optional — no
  `--sop-name` means every extracted statement is used, unchanged.

## Commands
```bash
uv sync
uv run sop-pipeline generate-mocks --north-star <path>                        # dev: north star -> mock inputs + manifest
uv run sop-pipeline run --inputs inputs/ --schema-guide <path>                # inputs/ -> out/sop_generated.md
uv run sop-pipeline run --inputs inputs/ --schema-guide <path> --sop <path>   # revise an existing SOP with new inputs
uv run sop-pipeline run --inputs inputs/ --schema-guide <path> --sop-name "PFML process"  # scope to one SOP
uv run sop-pipeline evaluate --north-star <path>                              # dev: score generated vs north star
uv run ruff check . && uv run ruff format .
```

## Models
- Synthesis + judging: `gpt-4o` (`SOP_SYNTH_MODEL` / `SOP_JUDGE_MODEL`).
- Per-file extraction (map step): `gpt-4o-mini` (`SOP_EXTRACT_MODEL`).
- Video frames + transcript: `gpt-4o` (`SOP_VIDEO_MODEL`); ASR `whisper-1`
  (`SOP_TRANSCRIBE_MODEL`).

## Inputs
`.docx` · `.md` · `.txt` · `.markdown` · `.mp4`· subdirectory of related documents.

## Gap types (from the schema guide)
`OPAQUE-RULE` (logic hidden in a rules DB) · `MISSING-DETAIL` (sources don't say) ·
`AMBIGUITY` (sources conflict) · `ASSUMPTION` (proceeded on an unconfirmed assumption) ·
`UNVERIFIED` (inherited claim neither confirmed nor contradicted) · `OUTDATED` (source
contradicts current behavior) · `MISSING-ARTIFACT` (a document that should exist does
not) · `PRODUCTION-READINESS` (documented but not fully live).
