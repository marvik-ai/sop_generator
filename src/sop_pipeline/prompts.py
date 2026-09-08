"""Load prompt files and fill {{TOKEN}} placeholders.

Placeholders use {{NAME}} (not str.format) so prompt bodies and injected SOP text can
contain literal braces without breaking rendering.
"""

from __future__ import annotations

import functools
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@functools.cache
def load_prompt(name: str) -> str:
    """Read a prompt file. Cached: a prompt is immutable for the length of a run."""
    path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, **values: str) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out
