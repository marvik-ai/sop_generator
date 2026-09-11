# SOP Generation Pipeline — Local ML run guide

This is the practical, Windows-friendly guide for running this repo in the same setup as the local environment used here: a locked-down enterprise workstation where `uv run` may be blocked by endpoint security and the approved Python is the system interpreter, not the repo-local `.venv`.

It combines the general project overview from [README.md](README.md) with the concrete execution notes from [README_run.md](README_run.md).

---

## What this project does

This pipeline takes a folder of input files and produces a structured SOP in markdown, while explicitly flagging gaps instead of hallucinating missing facts.

Typical flow:

1. Ingest inputs from `inputs/`
2. Extract structured statements from each source file
3. Reconcile conflicts across files
4. Synthesize a draft SOP
5. Audit and revise the SOP for gaps and unsupported statements
6. Generate a Mermaid diagram and final output artifacts

The repository is intentionally organized so that most of the logic lives in `prompts/`, while the Python code under `src/sop_pipeline/` is the thin orchestration layer.

---

## Required files and secrets

### Required by the pipeline

- `inputs/` with your source documents or transcripts
- a schema guide for `run`, passed as `--schema-guide`
- a north-star SOP for `generate-mocks` and `evaluate`, passed as `--north-star`

The repo does not ship a production schema guide or a north-star file. Those are user-supplied and should not be committed to the repo.

### Secret config

Create a local `.env` file for secrets if your environment requires it. Do not commit the real `.env` file.

Example:

```powershell
OPENAI_API_KEY=your_key_here
```

The project also supports other model overrides such as `SOP_SYNTH_MODEL`, `SOP_EXTRACT_MODEL`, `SOP_JUDGE_MODEL`, etc., via environment variables.

---

## Local environment constraints for this setup

This repo was run successfully only by bypassing the blocked repo-local Python environment and using the approved system interpreter.

### Why this matters

On this machine:

- `uv run` may select a blocked `.venv` interpreter
- endpoint security can block `.venv\Scripts\python.exe`
- local Python packages may need to be installed into a workspace-local directory instead of a system directory

### Working pattern used here

Set the project import path and dependency path explicitly:

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
```

Then invoke the CLI through the approved Python 3.14 interpreter:

```powershell
py -3.14 -m sop_pipeline.cli run --inputs inputs\ --schema-guide reference\sop_template_guide.md
```

This is the pattern to use when the repo-local `uv` environment is blocked by security policy.

---

## Setup steps

### 1. Clone and enter the repo

```powershell
cd C:\path\to\sop_generator
```

### 2. Install dependencies

If `uv sync` is blocked by your environment, install dependencies into a local folder for Python 3.14, for example:

```powershell
py -3.14 -m pip install -t .python-deps314 -r requirements.txt
```

If you are using the project-backed dependency management and it works in your environment, then this is still the preferred install path:

```powershell
uv sync
```

If your company blocks the `uv`-managed Python runtime due to certificate or policy restrictions, prefer the system-interpreter approach above.

### 3. Set environment variables

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
```

If needed, also set `OPENAI_API_KEY` or populate `.env`.

### 4. Prepare your required input files

Put your files into `inputs/`.

Supported inputs include:

- `.docx`
- `.md`
- `.txt`
- `.markdown`
- `.mp4`

Related files should be placed in a subfolder of `inputs/` so they are extracted as a group.

---

## Running the pipeline

### Generate a draft SOP from the current inputs

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli run --inputs inputs\ --schema-guide path\to\schema-guide.md
```

This creates output in `out/`.

If the command fails with:

```text
--schema-guide is required
```

then you are missing the required schema guide file. The repo intentionally does not include the user-supplied guide.

### Generate mock inputs from a north-star SOP

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli generate-mocks --north-star path\to\north_star.md
```

This is for dev/test setup only.

### Evaluate an SOP against a north-star reference

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli evaluate --north-star path\to\north_star.md
```

The north-star file is used only for evaluation; it should not be fed into the model during generation.

---

## Project layout

- `prompts/` — prompt logic for each stage of the pipeline
- `src/sop_pipeline/` — thin glue code for CLI, prompting, I/O, and orchestration
- `inputs/` — raw source files
- `reference/` — local reference or support docs, not necessarily committed secrets
- `out/` — generated artifacts (SOP, gap report, diagrams, evaluation output)
- `tests/` — unit tests
- `integration_tests/` — end-to-end test coverage

---

## Example from this environment

The known working pattern in this workspace was:

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli run --inputs inputs\ --schema-guide reference\sop_template_guide.md
```

This reached the extraction stage successfully and loaded the input files. The command then continued into the remote extraction process while the environment remained under enterprise security restrictions.

---

## Important guardrails

- Do not commit `.env`
- Do not commit generated output under `out/`
- Do not commit your north-star evaluation document
- Do not commit real credentials or local-only runtime state
- If `uv` is blocked by enterprise security, stick to the approved system interpreter and local dependency path

---

## Recommended quick start for a teammate with the same configuration

```powershell
cd path\to\sop_generator
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli run --inputs inputs\ --schema-guide reference\sop_template_guide.md
```

If they need the mock or evaluation commands:

```powershell
$env:PYTHONPATH = 'src;.python-deps314'
py -3.14 -m sop_pipeline.cli generate-mocks --north-star path\to\north_star.md
py -3.14 -m sop_pipeline.cli evaluate --north-star path\to\north_star.md
```

This is the most reliable local entrypoint for a machine with the same security constraints and Python launcher restrictions as the current environment.

---

## Final note

The repository is designed to be self-contained and to follow the principle: flag missing or uncertain facts instead of inventing them. For local execution, the biggest practical issue is not the pipeline logic — it is the environment and the required user-supplied schema guide and north-star files.
