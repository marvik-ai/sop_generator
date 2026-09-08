"""Validate and render Mermaid diagrams via the Mermaid CLI (`mmdc`).

Thin subprocess glue (no LLM). `mmdc` parses the diagram *before* it renders, so a
successful render is also our parse validation: one subprocess covers both the
"does it parse" guard and the "emit an image" deliverable.

The pipeline is otherwise pure-Python and self-contained, so `mmdc` is treated as an
*optional* host dependency: if neither a `mmdc` binary nor `npx` is on PATH, `render()`
returns `skipped=True` and the caller degrades to a warning rather than failing the run.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404 - mmdc is a trusted local tool, args are not user shell
import tempfile
from dataclasses import dataclass
from pathlib import Path


# mmdc shells out to a headless Chromium (puppeteer); in CI / sandboxed shells it must run
# with --no-sandbox or it crashes on launch. We hand mmdc this config via `-p`.
_PUPPETEER_CONFIG = {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
_RENDER_TIMEOUT_S = 120


@dataclass
class RenderResult:
    """Outcome of a single mmdc invocation.

    - ok: the diagram parsed and rendered.
    - error: mmdc's stderr (the parser error) when ok is False; empty otherwise.
    - image_path: the written image when ok is True; None otherwise.
    - skipped: mmdc was unavailable, so nothing was validated or rendered.
    """

    ok: bool
    error: str = ""
    image_path: Path | None = None
    skipped: bool = False


def _mmdc_command() -> list[str] | None:
    """Return the mmdc invocation to use, or None if mmdc is unavailable.

    Prefers a `mmdc` already on PATH; falls back to `npx -y @mermaid-js/mermaid-cli`
    (which fetches the CLI on demand) when only `npx` is present.
    """
    if shutil.which("mmdc"):
        return ["mmdc"]
    if shutil.which("npx"):
        return ["npx", "-y", "@mermaid-js/mermaid-cli"]
    return None


def render(mmd_source: str, out_path: Path) -> RenderResult:
    """Validate `mmd_source` by rendering it to `out_path` (format inferred from suffix).

    Returns a RenderResult: ok on a clean render, error carrying mmdc's stderr on a parse
    failure, or skipped when mmdc is not installed.
    """
    command = _mmdc_command()
    if command is None:
        return RenderResult(ok=False, skipped=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / "diagram.mmd"
        input_path.write_text(mmd_source, encoding="utf-8")
        puppeteer_path = tmp_dir / "puppeteer.json"
        puppeteer_path.write_text(json.dumps(_PUPPETEER_CONFIG), encoding="utf-8")

        try:
            proc = subprocess.run(  # noqa: S603 - command is a fixed local tool, no shell
                [
                    *command,
                    "-i",
                    str(input_path),
                    "-o",
                    str(out_path),
                    "-p",
                    str(puppeteer_path),
                ],
                capture_output=True,
                text=True,
                timeout=_RENDER_TIMEOUT_S,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as err:
            return RenderResult(ok=False, error=str(err))

    if proc.returncode == 0 and out_path.is_file():
        return RenderResult(ok=True, image_path=out_path)
    error = (proc.stderr or proc.stdout or "mmdc failed with no output").strip()
    return RenderResult(ok=False, error=error)


def validate(mmd_source: str) -> tuple[bool, str]:
    """Parse-check `mmd_source` without keeping an image.

    Convenience wrapper around render() to a throwaway temp file, for callers that only
    need the verdict. Returns (ok, error); a skipped (mmdc-unavailable) result reports
    ok=True so it never blocks on a missing optional dependency.
    """
    with tempfile.TemporaryDirectory() as tmp:
        result = render(mmd_source, Path(tmp) / "diagram.svg")
    if result.skipped:
        return True, ""
    return result.ok, result.error
