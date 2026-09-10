"""Integration test: pipeline.run() against the real OpenAI API, in revision mode.

Unlike test_pipeline.py / test_revise_from_sop.py (which monkeypatch llm.complete), this
file makes live calls through sop_pipeline.llm.complete, so it needs a real
OPENAI_API_KEY (see .env.example) and is skipped otherwise (not run by `uv run pytest`,
which is scoped to tests/ — invoke it explicitly).

Assertions are kept structural and template-agnostic: no assumptions about specific gap
IDs, section numbers, or wording of the (untracked, user-supplied) SOP being revised.
"""

from __future__ import annotations

import json
from pathlib import Path

from sop_pipeline import pipeline
from sop_pipeline.llm import _load_dotenv


_ROOT = Path(__file__).resolve().parents[1]
_INPUTS = _ROOT / "inputs_renew_sop_std"
_OLD_SOP = _ROOT / "out" / "fake_cropped_run" / "sop_generated.md"
_SCHEMA_GUIDE = _ROOT / "reference" / "sop_template_guide.md"

_load_dotenv()


def test_run_revises_an_existing_sop(tmp_path):
    sop_path = pipeline.run(_INPUTS, tmp_path, _SCHEMA_GUIDE, sop_path=_OLD_SOP)

    assert sop_path.is_file()
    text = sop_path.read_text(encoding="utf-8")
    assert len(text) > 1000

    extraction = json.loads((tmp_path / "extraction.json").read_text(encoding="utf-8"))
    assert isinstance(extraction, list) and extraction

    conflicts = json.loads((tmp_path / "conflicts.json").read_text(encoding="utf-8"))
    assert isinstance(conflicts, list)

    assert (tmp_path / "gaps_report.md").is_file()
