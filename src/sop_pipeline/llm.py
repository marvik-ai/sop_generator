"""Thin OpenAI wrapper: env/.env loading, model selection, one call helper."""

from __future__ import annotations

import base64
import datetime
import json
import os
from pathlib import Path

from openai import OpenAI


# Default models (overridable via env). Synthesis/judging use the most capable model;
# the per-file extraction map step uses a cheaper one.
DEFAULT_SYNTH_MODEL = "gpt-4o"
DEFAULT_EXTRACT_MODEL = "gpt-4o-mini"
DEFAULT_JUDGE_MODEL = "gpt-4o"
# The final `evaluate` grader is a SEPARATE knob from the generator's internal judge steps
# (reconcile / gap-audit / invariants). gpt-4.1 grades more reliably (honest TP/FN, summary
# consistent with the gap-by-gap trace), but using it for the generator's gap-audit prunes
# soft MISSING-DETAIL gaps and hurts recall — so the generator stays on the judge model and
# only the grader is upgraded here.
DEFAULT_EVAL_MODEL = "gpt-4.1"


def _load_dotenv() -> None:
    """Populate os.environ from the nearest .env without adding a dependency.

    Looks at sop_pipeline/.env first, then the repo-root .env. Existing environment
    variables always win.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / ".env",  # sop_pipeline/.env
        here.parents[3] / ".env",  # repo-root .env
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def _client() -> OpenAI:
    _load_dotenv()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in, "
            "or export it in your shell."
        )
    return OpenAI(api_key=key)


def synth_model() -> str:
    _load_dotenv()
    return os.environ.get("SOP_SYNTH_MODEL", DEFAULT_SYNTH_MODEL)


def extract_model() -> str:
    _load_dotenv()
    return os.environ.get("SOP_EXTRACT_MODEL", DEFAULT_EXTRACT_MODEL)


def judge_model() -> str:
    _load_dotenv()
    return os.environ.get("SOP_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)


def eval_model() -> str:
    """Model for the final `evaluate` grader only (see DEFAULT_EVAL_MODEL)."""
    _load_dotenv()
    return os.environ.get("SOP_EVAL_MODEL", DEFAULT_EVAL_MODEL)


def document_metadata() -> dict:
    """Section 1 document-control values (overridable via env), so they are never blank.

    `run_date` defaults to today; the rest fall back to sensible draft values.
    """
    _load_dotenv()
    return {
        "run_date": os.environ.get("SOP_RUN_DATE", datetime.date.today().isoformat()),
        "author": os.environ.get("SOP_AUTHOR", "TBD"),
        "version": os.environ.get("SOP_VERSION", "0.1 (draft)"),
        "status": os.environ.get("SOP_STATUS", "Draft"),
        "prepared_for": os.environ.get("SOP_PREPARED_FOR", "MyAwesomeCompany"),
    }


def complete(
    prompt: str,
    *,
    parts: list[dict] | None = None,
    model: str,
    system: str | None = None,
    max_tokens: int = 16000,
    temperature: float | None = None,
    response_format: dict | None = None,
) -> str:
    """Single-turn completion. Returns the response text.

    `parts` is optional and can contain text and/or images. If provided, parts are
    appended after `prompt` in the order given. Callers use the small internal
    vocabulary (`{"text": ...}` / `{"image_path": ...}`) and never touch the
    OpenAI content-part shape.

    Pass temperature=0 for reproducible output (e.g. the judge/eval steps, so scores
    don't drift run-to-run). Left as None to use the model's default otherwise.

    `response_format` is an optional JSON Schema (a plain dict, root `type: "object"`
    per the Structured Outputs requirement) describing the expected output shape. When
    given, it is wrapped into the API's `response_format: {"type": "json_schema", ...}`
    so the model is constrained to emit exactly that shape instead of merely being
    asked to in the prompt.
    """
    client = _client()
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})

    if parts:
        content = [{"type": "text", "text": prompt}, *_render_parts(parts)]
    else:
        content = prompt
    messages.append({"role": "user", "content": content})

    kwargs: dict = {"model": model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if response_format is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "extraction_output",
                "schema": response_format,
                "strict": True,
            },
        }

    try:
        resp = client.chat.completions.create(max_tokens=max_tokens, **kwargs)
    except Exception as err:  # noqa: BLE001
        # Newer reasoning models reject `max_tokens` in favor of
        # `max_completion_tokens`; retry once with the new parameter name.
        if "max_tokens" not in str(err):
            raise
        resp = client.chat.completions.create(
            max_completion_tokens=max_tokens, **kwargs
        )

    choice = resp.choices[0]
    if choice.finish_reason == "length":
        # A truncated structured-output body is invalid JSON, so the caller would otherwise
        # report a parse error for what is really an input too large for one call.
        raise RuntimeError(
            f"{model} stopped at the {max_tokens}-token output cap: the response is "
            f"truncated. Split the input or raise max_tokens."
        )
    return choice.message.content or ""


def parse_json_array(raw: str) -> list[dict]:
    """Tolerant JSON-array parse: strip code fences / surrounding prose if present."""
    text = raw.strip()
    if "```" in text:
        # take the content of the first fenced block
        parts = text.split("```")
        for part in parts:
            candidate = part
            if candidate.lstrip().startswith("json"):
                candidate = candidate.lstrip()[4:]
            candidate = candidate.strip()
            if candidate.startswith("["):
                text = candidate
                break
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


# --- Video / ASR -------------------------------------------------------------------
DEFAULT_VIDEO_MODEL = "gpt-5.1"
DEFAULT_TRANSCRIBE_MODEL = "whisper-1"
IMAGE_TOKENIZATION_LEVEL = "low"
_IMAGE_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def video_model() -> str:
    """Model for multimodal video extraction (see DEFAULT_VIDEO_MODEL)."""
    _load_dotenv()
    return os.environ.get("SOP_VIDEO_MODEL", DEFAULT_VIDEO_MODEL)


def transcribe_model() -> str:
    """Model for audio transcription only (see DEFAULT_TRANSCRIBE_MODEL)."""
    _load_dotenv()
    return os.environ.get("SOP_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL)


def _image_part(path: Path) -> dict:
    """Render one local image as an inline base64 data URL content part.

    `detail: "low"` pins the cost at ~85 tokens per image, which is what
    makes a few hundred frames affordable in a single call.
    """
    mime = _IMAGE_MIME_TYPES.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime};base64,{encoded}",
            "detail": IMAGE_TOKENIZATION_LEVEL,
        },
    }


def _render_parts(parts: list[dict]) -> list[dict]:
    """Translate this module's `{"text"} / {"image_path"}` vocabulary into API parts."""
    rendered: list[dict] = []
    for part in parts:
        if "image_path" in part:
            rendered.append(_image_part(Path(part["image_path"])))
        else:
            rendered.append({"type": "text", "text": str(part.get("text", ""))})
    return rendered


def _segment_field(segment: object, key: str, default: object = None) -> object:
    """Read a field off an SDK segment object or a plain dict (the SDK shape has moved)."""
    if isinstance(segment, dict):
        return segment.get(key, default)
    return getattr(segment, key, default)


def transcribe(audio_path: Path, *, model: str) -> list[dict]:
    """Transcribe one audio file into [{"start", "end", "text"}] segments.

    verbose_json plus segment granularity is the only response shape that carries
    timestamps. A response with no usable segments degrades to one segment spanning the
    whole chunk rather than losing the words — the caller can still cite the chunk.
    """
    client = _client()
    with audio_path.open("rb") as handle:
        resp = client.audio.transcriptions.create(
            file=handle,
            model=model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments: list[dict] = []
    for raw in getattr(resp, "segments", None) or []:
        text = str(_segment_field(raw, "text", "") or "").strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(_segment_field(raw, "start", 0.0) or 0.0),
                "end": float(_segment_field(raw, "end", 0.0) or 0.0),
                "text": text,
            }
        )
    if segments:
        return segments

    whole = str(getattr(resp, "text", "") or "").strip()
    if not whole:
        return []
    duration = float(getattr(resp, "duration", 0.0) or 0.0)
    return [{"start": 0.0, "end": duration, "text": whole}]
