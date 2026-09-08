---
name: extraction-test-guard
description: Use this skill whenever a file related to the extraction step of the sop_pipeline is modified — text extraction (src/sop_pipeline/ingest.py, src/sop_pipeline/pipeline.py, prompts/02_extract.md, prompts/02_extract_folder.md) or video extraction (src/sop_pipeline/video/*.py, prompts/02_extract_video.md) are triggers. Also use it if tests/test_extract.py or integration_tests/test_extract.py itself was edited. Not for unrelated files (synthesize/evaluate prompts, CLI, mocks, docs).
---

# Extraction pipeline test guard

## When to use

Trigger after you (Claude) finish editing any file that participates in the
extraction step of the pipeline:

- `src/sop_pipeline/ingest.py`
- `src/sop_pipeline/pipeline.py` (extraction-related changes)
- `src/sop_pipeline/video/*.py` (media.py, transcribe.py, naive.py, __init__.py)
- `prompts/02_extract.md`
- `prompts/02_extract_folder.md`
- `prompts/02_extract_video.md`
- `tests/test_extract.py`

Do not trigger for changes to unrelated prompts (`03_synthesize_sop.md`,
evaluate-related code), CLI-only changes, docs, or mocks.

## What to do

Run the bundled script:

```bash
bash .claude/skills/extraction-test-guard/run_tests.sh
```

Report the result to the user. If tests fail, show the failing test names
and the relevant assertion/error output, and fix the regression (or ask the
user how to proceed) before considering the edit complete — don't silently
continue with a broken extraction step.
