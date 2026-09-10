"""Orchestration: extract -> synthesize -> gap audit -> diagram, plus the evaluate stage.

Throughout this module, an "extracted statement" is one structured fact pulled from a
single source file (not to be confused with a CUSTOM_SYSTEM claim, which is the case the SOP
documents)."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from . import llm, mermaid, video
from .ingest import SourceDoc, combined_corpus, load_corpus
from .prompts import load_prompt, render
from .schema import DocExtraction, FilterOutput, FolderExtraction, ReconcileOutput
from .validate import (
    validate_branches,
    validate_diagram,
    validate_gap_ids,
    validate_systems_coverage,
)


SOP_TARGET_CUSTOMER = os.environ.get("SOP_TARGET_CUSTOMER", "MyAwesomeCompany")


class _ProgressBar:
    """A single sticky status line at the bottom of a run's output.

    `log()` prints a normal line (it scrolls up like any other print); the bar itself is
    only ever redrawn in place via `\r` + clear-to-end-of-line, never appended as a new
    line, so only one bar is ever visible at a time.
    """

    def __init__(self, width: int = 20):
        self._width = width
        self._percent = 0
        self._drawn = False

    def _bar_text(self) -> str:
        filled = round(self._width * self._percent / 100)
        bar = "█" * filled + "░" * (self._width - filled)
        return f"  [{bar}] {self._percent}%"

    def _redraw(self) -> None:
        sys.stdout.write(f"\r\033[K{self._bar_text()}")
        sys.stdout.flush()
        self._drawn = True

    def log(self, message: str) -> None:
        if self._drawn:
            sys.stdout.write("\r\033[K")
        print(message)
        self._redraw()

    def update(self, percent: int) -> None:
        self._percent = percent
        self._redraw()

    def finish(self) -> None:
        if self._drawn:
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._drawn = False


def _extract_one(doc: SourceDoc, template: str) -> list[dict]:
    """Map step: pull structured extracted statements from a single source file."""
    prompt = render(template, SOURCE_NAME=doc.name, SOURCE_TEXT=doc.text)
    raw = llm.complete(
        prompt,
        model=llm.extract_model(),
        max_tokens=8000,
        temperature=0,
        response_format=DocExtraction.model_json_schema(),
    )
    return json.loads(raw)["statements"]


def _hash(*parts: str) -> str:
    """SHA-256 over the parts joined by a NUL separator (used as a cache key)."""
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, doc: SourceDoc) -> Path:
    # A folder member's name is folder-qualified ("session_a/rec.mp4"); flatten it so the
    # entry stays one file and two same-named recordings in different folders can't collide.
    return cache_dir / f"{doc.name.replace('/', '_')}.json"


def _cached_statements(
    cache_dir: Path, doc: SourceDoc, prompt_text: str
) -> list[dict] | None:
    """Return cached statements if neither the file nor the extract prompt has changed."""
    path = _cache_path(cache_dir, doc)
    if not path.is_file():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if cached.get("hash") != _hash(prompt_text, doc.text):
        return None
    return cached.get("statements")


def _write_cache(
    cache_dir: Path, doc: SourceDoc, prompt_text: str, statements: list[dict]
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hash": _hash(prompt_text, doc.text),
        "statements": statements,
    }
    _cache_path(cache_dir, doc).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _file_sha256(path: Path) -> str:
    """SHA-256 over a file's bytes, read in chunks (a recording is too big to slurp)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _video_cache_key(doc: SourceDoc, prompt_text: str) -> str:
    """Cache key for a video: the strategy's knobs, the prompt and the file's bytes.

    doc.text cannot stand in for the content here (ingest leaves it empty), so the file's
    own hash does. `video.cache_key()` folds in the selected strategy's name and every
    decode parameter, because those decide what the model is actually shown — editing a knob
    (or switching strategy) must re-extract rather than mix two sampling plans.
    """
    return _hash(video.cache_key(), prompt_text, _file_sha256(doc.path))


def _cached_video(
    cache_dir: Path, doc: SourceDoc, prompt_text: str
) -> tuple[list[dict], str] | None:
    """Return cached (statements, audit corpus) if neither video nor prompt has changed."""
    path = _cache_path(cache_dir, doc)
    if not path.is_file():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if cached.get("hash") != _video_cache_key(doc, prompt_text):
        return None
    statements = cached.get("statements")
    if statements is None:
        return None
    return statements, cached.get("source_text", "")


def _write_video_cache(
    cache_dir: Path,
    doc: SourceDoc,
    prompt_text: str,
    statements: list[dict],
    source_text: str,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hash": _video_cache_key(doc, prompt_text),
        "statements": statements,
        "source_text": source_text,
    }
    _cache_path(cache_dir, doc).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _video_corpus(statements: list[dict]) -> str:
    """The gap-audit corpus for a recording: its evidence, one quote per line.

    `gap_audit` checks the SOP against the raw source text, and ingest leaves a video's
    `doc.text` empty — so without this every video-derived fact would be reported as an
    unsupported hallucination. The statements' verbatim quotes ARE that source text: a
    spoken line for a narrated fact, the literal rendered string for a screen-only one,
    each tagged with the timestamp where it was observed.
    """
    return "\n".join(
        f"- [{str(statement.get('supporting_media', '')).strip()}] {quote}"
        for statement in statements
        if (quote := str(statement.get("supporting_quote", "")).strip())
    )


def _extract_video(
    doc: SourceDoc,
    template: str,
    cache_dir: Path | None,
    force: bool,
) -> tuple[list[dict], bool]:
    """Map step for a recording: the video strategy -> statements. -> (found, cached).

    Unlike the text path this owns its own cache lookup, because the entry also carries
    the audit corpus and the key is over the file's bytes rather than over doc.text.
    """
    if not force and cache_dir is not None:
        cached = _cached_video(cache_dir, doc, template)
        if cached is not None:
            statements, source_text = cached
            doc.text = source_text
            return statements, True

    statements = video.extract(doc.path)
    doc.text = _video_corpus(statements)

    if cache_dir is not None:
        _write_video_cache(cache_dir, doc, template, statements, doc.text)
    return statements, False


def _extract_folder_one(
    doc: SourceDoc,
    template: str,
    text_members: list[SourceDoc],
    video_statements: list[dict],
) -> list[dict]:
    """One call over a folder's text documents plus its recordings' statements."""
    prompt = render(
        template,
        SOURCE_NAME=doc.name,
        SOURCE_TEXT=combined_corpus(text_members),
        VIDEO_STATEMENTS_JSON=json.dumps(
            video_statements, ensure_ascii=False, indent=2
        ),
    )
    raw = llm.complete(
        prompt,
        model=llm.extract_model(),
        max_tokens=16000,
        temperature=0,
        response_format=FolderExtraction.model_json_schema(),
    )
    return json.loads(raw)["statements"]


def _normalize_attribution(statements: list[dict], doc: SourceDoc) -> None:
    """Deterministically fix a folder statement's `source` / `supporting_media` pair.

    A folder has several member files, so the model names the one its evidence came from —
    and can name one that doesn't exist, or hand a timestamp to a text document (a meeting
    transcript's own `[12:07 PM]` speaker stamp reads like one). Neither is checkable, so:
    an unknown source falls back to the folder's own name, and `supporting_media` is cleared
    for anything not attributed to a recording — it means a position in a recording, and
    nothing else can supply one.
    """
    member_names = {member.name for member in doc.members}
    video_names = {member.name for member in doc.members if member.is_video()}
    for statement in statements:
        if statement.get("source") not in member_names:
            statement["source"] = doc.name
        if statement["source"] not in video_names:
            statement["supporting_media"] = ""


def _extract_member_videos(
    doc: SourceDoc, video_template: str, cache_dir: Path | None, force: bool
) -> tuple[list[dict], bool]:
    """Every recording in the folder -> (statements, all came from cache).

    Each statement is tagged with the member it came from here rather than in `extract`'s
    loop: the folder prompt has to be able to name the recording a fact was observed in,
    and it only ever sees these statements as JSON.
    """
    statements: list[dict] = []
    all_cached = True
    for member in doc.members:
        if not member.is_video():
            continue
        found, cached = _extract_video(member, video_template, cache_dir, force)
        all_cached = all_cached and cached
        for statement in found:
            statement["source"] = member.name
        statements.extend(found)
    return statements, all_cached


def _extract_folder(
    doc: SourceDoc,
    template: str,
    video_template: str,
    cache_dir: Path | None,
    force: bool,
) -> tuple[list[dict], bool]:
    """Map step for a folder of related documents -> ONE fused list. -> (found, cached).

    Member recordings are extracted first, then their statements and the folder's merged
    text go to a single call. That one call is what lets the model consolidate a fact three
    files agree on and keep both versions of one they don't. Only the fused list is returned:
    the recordings' own facts live on inside it, `supporting_media` included.

    The videos must run before `doc.text` is built — the text cache key is taken over it, and
    a recording's contribution to it is the evidence `_extract_video` fills in. A folder
    holding nothing but recordings skips the fused call: it has nothing to fuse them with.
    """
    video_statements, videos_cached = _extract_member_videos(
        doc, video_template, cache_dir, force
    )
    doc.text = combined_corpus(doc.members)

    text_members = [member for member in doc.members if not member.is_video()]
    if not text_members:
        # Nothing to fuse with: the call could only re-emit what it was just handed.
        return video_statements, videos_cached

    # doc.text carries each recording's quotes and timestamps but not the rest of its
    # statements, which the fused call also reads — so they are part of the key too.
    key_text = template + json.dumps(
        video_statements, ensure_ascii=False, sort_keys=True
    )
    cached = (
        None
        if force or cache_dir is None
        else _cached_statements(cache_dir, doc, key_text)
    )
    if cached is not None:
        return cached, True

    statements = _extract_folder_one(doc, template, text_members, video_statements)
    _normalize_attribution(statements, doc)
    if cache_dir is not None:
        _write_cache(cache_dir, doc, key_text, statements)
    return statements, False


def _strip_code_fence(raw: str) -> str:
    """Drop a ``` fence if the model wrapped its output despite instructions."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
    return text.strip()


def _extract_doc(
    doc: SourceDoc, cache_dir: Path | None, force: bool
) -> tuple[list[dict], bool]:
    """Route one input to its branch. -> (statements, came_from_cache)."""
    if doc.is_folder():
        return _extract_folder(
            doc,
            load_prompt("02_extract_folder.md"),
            load_prompt(video.prompt_name()),
            cache_dir,
            force,
        )
    if doc.is_video():
        return _extract_video(doc, load_prompt(video.prompt_name()), cache_dir, force)

    template = load_prompt("02_extract.md")
    found = (
        None
        if force or cache_dir is None
        else _cached_statements(cache_dir, doc, template)
    )
    if found is not None:
        return found, True
    found = _extract_one(doc, template)
    if cache_dir is not None:
        _write_cache(cache_dir, doc, template, found)
    return found, False


def extract(
    docs: list[SourceDoc],
    cache_dir: Path | None = None,
    force: bool = False,
    bar: _ProgressBar | None = None,
) -> list[dict]:
    """Extract statements from every file and tag each with its source.

    If cache_dir is given, skip the LLM call for any file whose content AND the extract
    prompt both match a previous extraction (pass force=True to bypass the cache). Editing
    02_extract.md changes the cache key, so the cache is rebuilt automatically.

    Recordings take the video branch — the strategy selected in `video/config.yaml`, see
    `video/README.md` — and produce the same statement list. A folder of related documents
    takes the folder branch and produces ONE fused statement list for the whole folder (see
    `_extract_folder`).
    """
    statements: list[dict] = []
    total = len(docs)
    for index, doc in enumerate(docs):
        found, cached = _extract_doc(doc, cache_dir, force)
        for statement in found:
            statement.setdefault("source", doc.name)
        statements.extend(found)
        suffix = " (cached, unchanged)" if cached else ""
        message = f"  extracted {len(found)} statements from {doc.name}{suffix} ✅"
        if bar is not None:
            bar.log(message)
            bar.update(round((index + 1) / total * 40) if total else 40)
        else:
            print(message)
    return statements


def _statements_hash(statements: list[dict], prompt_text: str) -> str:
    """Cache key for a statement-set stage (filter/reconcile): the statements plus the
    stage's prompt (and, for filter, the sop_name folded into prompt_text by the caller)."""
    canonical = json.dumps(statements, ensure_ascii=False, sort_keys=True)
    return _hash(prompt_text, canonical)


def _filter_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "filter_cache.json"


def _cached_filtered(
    cache_dir: Path, statements: list[dict], prompt_text: str
) -> list[dict] | None:
    """Return cached filtered statements if neither the statements nor the filter
    prompt+SOP name (folded into prompt_text by the caller) changed."""
    path = _filter_cache_path(cache_dir)
    if not path.is_file():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if cached.get("hash") != _statements_hash(statements, prompt_text):
        return None
    return cached.get("statements")


def _write_filter_cache(
    cache_dir: Path, statements: list[dict], prompt_text: str, filtered: list[dict]
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hash": _statements_hash(statements, prompt_text),
        "statements": filtered,
    }
    _filter_cache_path(cache_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _sop_identifier_block(sop_name: str, sop_description: str) -> str:
    lines = []
    if sop_name:
        lines.append(f"Name: {sop_name}")
    if sop_description:
        lines.append(f"Description: {sop_description}")
    return "\n".join(lines)


def filter_by_sop(
    statements: list[dict],
    sop_name: str,
    sop_description: str = "",
    cache_dir: Path | None = None,
    force: bool = False,
) -> list[dict]:
    """Keep only the statements relevant to the named SOP (e.g. "PFML process").

    A single input folder can mix material from several distinct processes; this lets a
    run scope itself to one of them before reconcile/synthesize see the statements. With
    neither sop_name nor sop_description, this is a no-op — every statement passes through
    unchanged.

    The model is asked to return the indices to keep, not to re-emit statement objects:
    statement shapes vary (FolderStatement adds source/supporting_media on top of
    DocStatement) and round-tripping them through a strict output schema risks losing
    those extra fields or letting the model reword a statement. Selecting by index keeps
    the actual filtering judgment in the prompt while the indexing is deterministic glue.

    If cache_dir is given, skip the LLM call when both the statement set and the filter
    prompt+sop_name+sop_description are unchanged since the last filter run (pass
    force=True to bypass).
    """

    if not sop_name and not sop_description:
        return statements

    template = load_prompt("02b_filter_by_sop.md")
    prompt_key = template + sop_name + sop_description
    if not force and cache_dir is not None:
        cached = _cached_filtered(cache_dir, statements, prompt_key)
        if cached is not None:
            print("  filter: cached (unchanged)")
            return cached

    indexed = [
        {
            "index": index,
            "target_section": statement.get("target_section", ""),
            "statement": statement.get("statement", ""),
            "source": statement.get("source", ""),
        }
        for index, statement in enumerate(statements)
    ]
    prompt = render(
        template,
        SOP_IDENTIFIER=_sop_identifier_block(sop_name, sop_description),
        STATEMENTS_JSON=json.dumps(indexed, ensure_ascii=False, indent=2),
    )
    raw = llm.complete(
        prompt,
        model=llm.judge_model(),
        max_tokens=4000,
        temperature=0,
        response_format=FilterOutput.model_json_schema(),
    )
    keep_indices = json.loads(raw)["keep_indices"]
    filtered = [
        statements[index] for index in keep_indices if 0 <= index < len(statements)
    ]
    if cache_dir is not None:
        _write_filter_cache(cache_dir, statements, prompt_key, filtered)
    return filtered


def _reconcile_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "reconcile_cache.json"


def _cached_conflicts(
    cache_dir: Path, statements: list[dict], prompt_text: str
) -> list[dict] | None:
    """Return cached conflicts if neither the statements nor the reconcile prompt changed."""
    path = _reconcile_cache_path(cache_dir)
    if not path.is_file():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if cached.get("hash") != _statements_hash(statements, prompt_text):
        return None
    return cached.get("conflicts")


def _write_reconcile_cache(
    cache_dir: Path, statements: list[dict], prompt_text: str, conflicts: list[dict]
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hash": _statements_hash(statements, prompt_text),
        "conflicts": conflicts,
    }
    _reconcile_cache_path(cache_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def reconcile(
    statements: list[dict],
    cache_dir: Path | None = None,
    force: bool = False,
    existing_sop: str = "",
) -> list[dict]:
    """Reduce step: compare statements across ALL sources and flag value-conflicts.

    Extraction is a per-file map, so a statement's `conflicts_with` field can never see
    other files. This stage receives every statement at once and surfaces same-subject
    differing-value disagreements (e.g. a 5-day vs 10-day threshold) for synthesis to
    render as AMBIGUITY gaps.

    If cache_dir is given, skip the LLM call when both the statement set and the reconcile
    prompt are unchanged since the last reconciliation (pass force=True to bypass). Editing
    07_reconcile.md changes the cache key, so the cache is rebuilt automatically.

    `existing_sop`, when given, appends the `07b_reconcile_with_sop.md` overlay so the old
    SOP's confident assertions are also compared against the new statements.
    """
    template = load_prompt("07_reconcile.md")
    if existing_sop:
        template += "\n\n" + load_prompt("07b_reconcile_with_sop.md")
    if not force and cache_dir is not None:
        cached = _cached_conflicts(cache_dir, statements, template + existing_sop)
        if cached is not None:
            print("  reconcile: cached (unchanged)")
            return cached

    prompt = render(
        template,
        STATEMENTS_JSON=json.dumps(statements, ensure_ascii=False, indent=2),
        EXISTING_SOP=existing_sop,
    )
    raw = llm.complete(
        prompt,
        model=llm.judge_model(),
        max_tokens=4000,
        temperature=0,
        response_format=ReconcileOutput.model_json_schema(),
    )
    conflicts = json.loads(raw)["conflicts"]
    if cache_dir is not None:
        _write_reconcile_cache(
            cache_dir, statements, template + existing_sop, conflicts
        )
    return conflicts


def synthesize(
    statements: list[dict],
    schema_guide: str,
    conflicts: list[dict] | None = None,
    metadata: dict | None = None,
    existing_sop: str = "",
    existing_sop_name: str = "",
    new_input_names: list[str] | None = None,
) -> str:
    """Synthesize the full SOP markdown from extracted statements + the schema guide.

    `conflicts` are cross-file disagreements from the reconcile stage; each must be
    rendered as an AMBIGUITY gap. `metadata` fills Section 1 document-control fields
    (run date, author, version, status) so they are never left as placeholders/gaps.

    `existing_sop`, when given, appends the `03b_revise_existing_sop.md` overlay so the
    model revises that SOP in place instead of writing a from-scratch one — with no SOP
    this is a no-op and the base prompt reaches the model unchanged. `existing_sop_name`
    and `new_input_names` tell that overlay what to cite in Section 1's "Source
    documents" (the existing SOP file itself, not its own transitive source list, plus
    this revision's new inputs).
    """
    metadata = metadata or {}
    template = load_prompt("03_synthesize_sop.md")
    if existing_sop:
        template += "\n\n" + load_prompt("03b_revise_existing_sop.md")
    prompt = render(
        template,
        SCHEMA_GUIDE=schema_guide,
        STATEMENTS_JSON=json.dumps(statements, ensure_ascii=False, indent=2),
        CONFLICTS_JSON=json.dumps(conflicts or [], ensure_ascii=False, indent=2),
        RUN_DATE=metadata.get("run_date", "TBD"),
        AUTHOR=metadata.get("author", "TBD"),
        VERSION=metadata.get("version", "0.1 (draft)"),
        EXISTING_SOP=existing_sop,
        EXISTING_SOP_NAME=existing_sop_name,
        NEW_INPUT_FILES=", ".join(new_input_names or []),
        STATUS=metadata.get("status", "Draft"),
    )
    return llm.complete(
        prompt, model=llm.synth_model(), max_tokens=16384, temperature=0
    ).strip()


def revise(sop_md: str, audit_report: str) -> str:
    """Patch the SOP in place using the gap-audit findings (Section 10 + inline tags)."""
    template = load_prompt("08_revise.md")
    prompt = render(template, SOP=sop_md, AUDIT=audit_report)
    return llm.complete(
        prompt, model=llm.synth_model(), max_tokens=16384, temperature=0
    ).strip()


_HEADING_RE = re.compile(r"^#{1,6}\s")
_SECTION1_RE = re.compile(r"^#{1,6}\s*1\.\s")
_GAP_TAG_RE = re.compile(r"\s*\[GAP\s+G-\d+\]")
_TABLE_ROW_RE = re.compile(r"^\s*\|([^|]+)\|(.*)\|\s*$")
# Section 1 document-control fields the run already knows the value of (label -> metadata key).
_METADATA_FIELDS = {
    "last updated": "run_date",
    "author / owner": "author",
    "version": "version",
    "status": "status",
}


def _normalize_section1(sop_md: str, metadata: dict) -> str:
    """Deterministically fix the Section 1 metadata table.

    The synth model occasionally mis-tags document-control fields (e.g. dropping a
    `[GAP G-xx]` onto Last updated / Author). Those values are known up front, so rather
    than rely on the prompt we overwrite the known fields from `metadata` and strip any
    stray gap tags from the Section 1 table. Only Section 1 is touched; process gaps in the
    body are left alone.
    """
    out: list[str] = []
    in_section1 = False
    for line in sop_md.splitlines():
        if _HEADING_RE.match(line):
            in_section1 = bool(_SECTION1_RE.match(line))
            out.append(line)
            continue
        if in_section1:
            line = _normalize_section1_line(line, metadata)
        out.append(line)
    return "\n".join(out)


def _normalize_section1_line(line: str, metadata: dict) -> str:
    match = _TABLE_ROW_RE.match(line)
    if match is None:
        return _GAP_TAG_RE.sub("", line)
    label, _value = match.group(1).strip(), match.group(2)
    key = _METADATA_FIELDS.get(label.lower())
    if key and metadata.get(key):
        return f"| {label} | {metadata[key]} |"
    return _GAP_TAG_RE.sub("", line)


def synthesize_invariants(sop_md: str) -> str:
    """LLM call: derive a small cross-cutting invariants table from content already in the SOP.

    Unlike the front matter / TOC / checkpoint index below, invariants require reading and
    summarizing the finished body (e.g. "no rejection write-back" or "every exit produces
    one structured summary") rather than a transform of already-known values, so this is
    the one piece of structural parity that still needs the model.
    """
    template = load_prompt("09_invariants.md")
    prompt = render(template, SOP=sop_md)
    raw = llm.complete(prompt, model=llm.judge_model(), max_tokens=2000, temperature=0)
    return _strip_code_fence(raw)


_NON_SLUG_RE = re.compile(r"[^a-z0-9 -]")


def _slugify(heading_text: str) -> str:
    """GitHub-style anchor slug matching the north star's TOC anchors.

    Lowercase, drop everything outside [a-z0-9 -], then turn each remaining space into a
    '-' (no run-collapsing) — this is what reproduces double-hyphen anchors like
    '#1-document-control--metadata' where a '/' was removed between two spaces.
    """
    return _NON_SLUG_RE.sub("", heading_text.lower()).replace(" ", "-")


_NON_SLUG_CHARS_RE = re.compile(r"[^a-z0-9]+")


def _sop_name_slug(sop_name: str, max_length: int = 20) -> str:
    """Filesystem-safe fragment for the output filename (sop_<slug>.md)."""
    slug = _NON_SLUG_CHARS_RE.sub("_", sop_name.lower()).strip("_")
    return slug[:max_length].rstrip("_")


_LEVEL2_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_NUMBERED_HEADING_RE = re.compile(r"^(\d+)\.\s*(.+)$")


def _table_of_contents(sop_md: str) -> str:
    """Auto-generate the Table of Contents from the document's '## ' headings.

    Numbered sections become a numbered TOC entry; unnumbered ones (Annex 1, Appendix A)
    become a bullet — matching the north star's TOC shape. Must be called after Annex 1
    and Appendix A have already been appended so they're included.
    """
    lines: list[str] = []
    for heading_text in _LEVEL2_HEADING_RE.findall(sop_md):
        heading_text = heading_text.strip()
        slug = _slugify(heading_text)
        numbered = _NUMBERED_HEADING_RE.match(heading_text)
        if numbered:
            num, title = numbered.groups()
            lines.append(f"{num}. [{title}](#{slug})")
        else:
            lines.append(f"- [{heading_text}](#{slug})")
    return "\n".join(lines)


_VERSION_NUM_RE = re.compile(r"(\d+)\.(\d+)")


def _bump_version(version: str) -> str:
    """Increment the minor version number by 1 (e.g. '0.1 (draft)' -> '0.2 (draft)')."""
    match = _VERSION_NUM_RE.search(version)
    if not match:
        return version
    major, minor = match.groups()
    return _VERSION_NUM_RE.sub(f"{major}.{int(minor) + 1}", version, count=1)


def _extract_section1_field(sop_md: str, label: str) -> str | None:
    """Pull a labeled value out of the (already-finalized) Section 1 metadata table."""
    in_section1 = False
    for line in sop_md.splitlines():
        if _HEADING_RE.match(line):
            in_section1 = bool(_SECTION1_RE.match(line))
            continue
        if not in_section1:
            continue
        match = _TABLE_ROW_RE.match(line)
        if match and match.group(1).strip().lower() == label.lower():
            return match.group(2).strip()
    return None


_INTRO_TEMPLATE = (
    "This SOP is the business specification of how the **{title}** process is carried "
    "out. It is written to be (1) verifiable by an LLM-as-judge against an agent's "
    "execution trace, and (2) usable by a developer to build/extend the agent. It "
    "describes what must happen and why, not the code that does it."
)
_COMPLETENESS_NOTE = (
    "**Completeness note:** This is a draft that maps every known pathway this process "
    "can take. Many decision points depend on business rules that today live in a rules "
    "database or in customer-specific configuration and are not yet confirmed. Every "
    "such hole is marked inline as `[GAP G-xx]` and listed in Section 10. The SOP will "
    "be completed iteratively with the client; gaps are surfaced, never invented."
)


def _front_matter(sop_md: str, metadata: dict) -> str:
    """Deterministic title / prepared-for-by / intro block prepended ahead of Section 1.

    Pulled entirely from the already-finalized Section 1 table plus the run's metadata —
    never from the LLM — so it can never drift into a placeholder or a stray gap tag.
    """
    title = _extract_section1_field(sop_md, "SOP title") or "Untitled process"
    lines = [f"# SOP — {title}", ""]
    run_date = metadata.get("run_date", "")
    try:
        month_year = datetime.date.fromisoformat(run_date).strftime("%B %Y")
        lines += [f"**{month_year}**", ""]
    except ValueError:
        pass
    lines += [
        f"**Prepared for:** {metadata.get('prepared_for', SOP_TARGET_CUSTOMER)}",
        f"**Prepared by:** {metadata.get('author', 'TBD')}",
        "",
        "---",
        "",
        _INTRO_TEMPLATE.format(title=title),
        "",
        _COMPLETENESS_NOTE,
    ]
    return "\n".join(lines)


_STEP_HEADING_RE = re.compile(r"^### Step (\d+) — ")
_TOP_BULLET_FIELD_RE = re.compile(r"^-\s*\*\*([^*]+):\*\*\s*(.*)$")
_SUB_BULLET_RE = re.compile(r"^\s+[-*]\s+(.+)$")
_GAP_ID_RE = re.compile(r"\bG-\d+\b")
_PLAN_SCOPE_RE = re.compile(r"\b(?:every|each|all)\b.{0,30}\bplans?\b", re.IGNORECASE)
_EVENT_SCOPE_RE = re.compile(r"\bevent\b", re.IGNORECASE)


def _checkpoint_scope(text: str) -> str:
    """Best-effort scope label for a checkpoint bullet (not a hard correctness guarantee)."""
    if _PLAN_SCOPE_RE.search(text):
        return "Per-plan"
    if _EVENT_SCOPE_RE.search(text):
        return "Per-event"
    return "Per-claim"


def _harvest_checkpoints(sop_md: str) -> list[dict]:
    """Pull each step's Evaluation-checkpoint bullets + related gap IDs.

    Pure structural parse of the Section 6 step blocks (steps are real `### Step N — ...`
    headings; see the synthesize prompt). Returns one dict per checkpoint:
    {"id": "STEP2-C1", "step": 2, "text": "...", "related_gaps": "G-05" | "—"}.
    """
    checkpoints: list[dict] = []
    step_num: int | None = None
    current_field: str | None = None
    field_lines: dict[str, list[str]] = {}

    def flush_step() -> None:
        if step_num is None:
            return
        checkpoint_lines = field_lines.get("evaluation checkpoints", [])
        gaps_text = " ".join(field_lines.get("open questions / gaps", []))
        related = ", ".join(dict.fromkeys(_GAP_ID_RE.findall(gaps_text))) or "—"
        for i, text in enumerate(checkpoint_lines, start=1):
            checkpoints.append(
                {
                    "id": f"STEP{step_num}-C{i}",
                    "step": step_num,
                    "text": text,
                    "related_gaps": related,
                }
            )

    for line in sop_md.splitlines():
        step_match = _STEP_HEADING_RE.match(line)
        if step_match:
            flush_step()
            step_num = int(step_match.group(1))
            current_field = None
            field_lines = {}
            continue
        if step_num is None:
            continue
        if _HEADING_RE.match(line):
            flush_step()
            step_num = None
            current_field = None
            field_lines = {}
            continue
        top_match = _TOP_BULLET_FIELD_RE.match(line)
        if top_match:
            current_field = top_match.group(1).strip().lower()
            field_lines.setdefault(current_field, [])
            inline_value = top_match.group(2).strip()
            if inline_value and inline_value.lower() != "none":
                field_lines[current_field].append(inline_value)
            continue
        sub_match = _SUB_BULLET_RE.match(line)
        if sub_match and current_field:
            field_lines[current_field].append(sub_match.group(1).strip())
    flush_step()
    return checkpoints


_APPENDIX_A_INTRO = (
    "This appendix is **not part of the original SOP body**. It consolidates every "
    '"Evaluation checkpoint" from Section 6 into a single, individually-addressable list '
    "so an LLM-as-judge can score an agent's execution trace assertion-by-assertion. Each "
    "checkpoint carries a stable ID (`STEP<n>-C<m>`), the assertion to verify, a scope, "
    "and related gap IDs that may make the assertion unverifiable until the gap is closed."
)


def _appendix_a(checkpoints: list[dict], invariants_md: str) -> str:
    """Deterministically render the checkpoint index; splice in the LLM-derived invariants."""
    lines = [
        "## Appendix A: Machine-readable evaluation checkpoint index",
        "",
        _APPENDIX_A_INTRO,
        "",
        "| Checkpoint ID | Step | Scope | Assertion to verify against the trace | "
        "Related gaps |",
        "|---|---|---|---|---|",
    ]
    for cp in checkpoints:
        scope = _checkpoint_scope(cp["text"])
        lines.append(
            f"| {cp['id']} | {cp['step']} | {scope} | {cp['text']} | "
            f"{cp['related_gaps']} |"
        )
    lines += [
        "",
        f"**Total checkpoints: {len(checkpoints)}**",
        "",
        invariants_md.strip(),
    ]
    return "\n".join(lines)


def _validation_warnings_md(structural: list[str], diagram: list[str]) -> str:
    """Render the deterministic validation warnings as a markdown section for the report.

    Groups the gap-id/fork-branch warnings and the flow-diagram parity warnings under one
    heading. Always returns a section (an explicit "no warnings" line when both are empty)
    so the report unambiguously records that the checks ran.
    """
    lines = [
        "## Deterministic validation warnings",
        "",
        "These are produced by structural checks (not the LLM audit above).",
        "",
    ]
    if not structural and not diagram:
        lines.append("No deterministic validation warnings.")
        return "\n".join(lines)
    if structural:
        lines += ["### Gap-ID & fork-branch checks", ""]
        lines += [f"- {w}" for w in structural]
        lines.append("")
    if diagram:
        lines += ["### Flow-diagram parity (Annex 1)", ""]
        lines += [f"- {w}" for w in diagram]
        lines.append("")
    return "\n".join(lines).rstrip()


def _diagram_advisory(diagram_warnings: list[str]) -> str:
    """A short blockquote for Annex 1 when the diagram fails parity checks (else empty)."""
    if not diagram_warnings:
        return ""
    return (
        '> ⚠️ This diagram is known to be incomplete — see the "Deterministic validation '
        'warnings" section of gaps_report.md. Some declared IF/THEN branches and Section 9 '
        "end states are not represented as edges/terminal nodes.\n\n"
    )


def generate_diagram(sop_md: str, parser_feedback: str = "") -> str:
    """Generate a Mermaid flowchart (TD) mirroring the SOP's Section 6 steps.

    `parser_feedback` is empty on the first attempt; on a retry it carries the previous
    Mermaid parser error so the model can fix the broken output (see build_diagram).
    """
    template = load_prompt("06_generate_diagram.md")
    prompt = render(template, SOP=sop_md, PARSER_FEEDBACK=parser_feedback)
    raw = llm.complete(
        prompt, model=llm.synth_model(), max_tokens=4000, temperature=0
    ).strip()
    return _strip_code_fence(raw)


def _parser_feedback(error: str) -> str:
    """Retry instruction injected into the diagram prompt after a parse failure."""
    return (
        "## RETRY — your previous diagram did not parse\n\n"
        "Your last attempt failed to render with this Mermaid parser error:\n\n"
        f"```\n{error}\n```\n\n"
        "Fix it. The most common cause is a forbidden character in a node label or edge "
        "label — re-read the 'Mermaid syntax safety' section below and remove any of the "
        "banned characters. Output only corrected Mermaid source."
    )


def build_diagram(
    sop_md: str, out_dir: Path, bar: _ProgressBar | None = None
) -> tuple[str, list[str]]:
    """Generate, validate (parse + render to SVG), and consistency-check the diagram.

    Validation uses the Mermaid CLI: a successful render is the parse check and also emits
    `out/sop_flow_diagram.svg`. On a parse failure the diagram is regenerated once with the
    parser error fed back into the prompt. Returns the (possibly retried) Mermaid source and
    a list of advisory warnings to surface in the run output. If the CLI is unavailable the
    render/parse guard is skipped (warned), but the consistency check still runs.
    """
    warnings: list[str] = []
    mermaid_src = generate_diagram(sop_md)
    svg_path = out_dir / "sop_flow_diagram.svg"
    result = mermaid.render(mermaid_src, svg_path)

    if result.skipped:
        warnings.append(
            "mmdc (Mermaid CLI) not found; skipped diagram parse validation and SVG "
            "render. Install Node + @mermaid-js/mermaid-cli to enable them."
        )
    elif not result.ok:
        message = "  diagram failed to parse; retrying once with the parser error..."
        if bar is not None:
            bar.log(message)
        else:
            print(message)
        mermaid_src = generate_diagram(
            sop_md, parser_feedback=_parser_feedback(result.error)
        )
        result = mermaid.render(mermaid_src, svg_path)
        if not result.ok:
            warnings.append(
                f"Generated Mermaid still fails to parse after one retry: {result.error}"
            )

    # Don't let a stale SVG from a previous run get linked when this run produced none.
    if not result.ok and svg_path.is_file():
        svg_path.unlink()

    warnings.extend(validate_diagram(sop_md, mermaid_src))
    return mermaid_src, warnings


def gap_audit(sop_md: str, corpus: str) -> str:
    """Self-critique: flag hallucinations and gaps that should have been raised."""
    template = load_prompt("04_gap_audit.md")
    prompt = render(template, SOP=sop_md, CORPUS=corpus)
    return llm.complete(
        prompt, model=llm.judge_model(), max_tokens=8000, temperature=0
    ).strip()


_SECTION10_ROW_RE = re.compile(
    r"^\|\s*(?P<id>G-\d+)\s*\|[^|]*\|[^|]*\|\s*(?P<question>[^|]+?)\s*\|",
    re.MULTILINE,
)


def _check_manifest_rules(sop_md: str, manifest: str = "") -> str:
    """Deterministic keyword-based pre-verification for MF-01, MF-03, MF-04.

    Returns a markdown block that is injected into the evaluate prompt so the LLM
    judge cannot override the TP/FN verdict for simple literal-match rules. MF-02
    (Applicability value→bucket mapping) still uses the LLM's judgment because the
    rule requires distinguishing two topically-similar things.

    These keyword rules are specific to the Absence north-star manifest. Each row is
    only emitted when its manifest ID is actually present in `manifest`, so a different
    scenario (e.g. the branching demo) is graded by the LLM judge against its own
    manifest without inheriting Absence-specific FIXED verdicts.
    """
    rows = {
        m.group("id"): m.group("question").lower()
        for m in _SECTION10_ROW_RE.finditer(sop_md)
    }

    def _find(cond) -> tuple[str, str]:
        for gid, q in rows.items():
            if cond(q):
                return gid, q
        return "none raised", ""

    mf01_id, mf01_q = _find(lambda q: "pilot" in q and ("list" in q or "customer" in q))
    mf01_verdict = "TP" if mf01_id != "none raised" else "FN"

    mf03_id, mf03_q = _find(lambda q: "screen" in q or "field" in q)
    mf03_verdict = "TP" if mf03_id != "none raised" else "FN"

    mf04_id, mf04_q = _find(lambda q: "5 day" in q and "10 day" in q)
    mf04_verdict = "TP" if mf04_id != "none raised" else "FN"

    def _row(mfid, gid, verdict, q):
        quote = f'"{q}"' if q else "none raised"
        return f"| {mfid} | {gid} | {verdict} | {quote} |"

    # Only emit a pre-verified row when its manifest ID is in scope for this run. When no
    # manifest is supplied (legacy callers), keep the original Absence behaviour.
    candidate_rows = [
        ("MF-01", _row("MF-01", mf01_id, mf01_verdict, mf01_q)),
        ("MF-03", _row("MF-03", mf03_id, mf03_verdict, mf03_q)),
        ("MF-04", _row("MF-04", mf04_id, mf04_verdict, mf04_q)),
    ]
    active = [row for mfid, row in candidate_rows if not manifest or mfid in manifest]
    if not active:
        return (
            "No deterministic keyword pre-checks apply to this manifest; grade every "
            "manifest row with your own judgment against the supplied manifest rules."
        )

    lines = [
        "The table below is the output of a **deterministic Python keyword check** "
        "against Section 10. These verdicts are computed from literal substring "
        "matches — they are FIXED. Copy them verbatim into the corresponding "
        "rows of your gap-by-gap trace table; do not change Matched Gap ID or Verdict "
        "for these rows.",
        "",
        "| Manifest ID | Matched Gap ID | Verdict | Question text (lower-cased) |",
        "|---|---|---|---|",
        *active,
        "",
        "MF-02 is NOT included here — its rule requires distinguishing two topically-"
        "similar gaps and is left to your judgment.",
    ]
    return "\n".join(lines)


def evaluate(sop_md: str, north_star: str, manifest: str) -> str:
    """LLM-judge: reconstruction coverage + gap accuracy vs the north star."""
    pre_check = _check_manifest_rules(sop_md, manifest)
    template = load_prompt("05_evaluate_vs_reference.md")
    prompt = render(
        template,
        GENERATED=sop_md,
        NORTH_STAR=north_star,
        MANIFEST=manifest,
        PRE_VERIFIED=pre_check,
    )
    return llm.complete(
        prompt, model=llm.eval_model(), max_tokens=8000, temperature=0
    ).strip()


def _without_existing_sop(
    docs: list[SourceDoc], inputs_dir: Path, sop_path: Path | None
) -> list[SourceDoc]:
    """Drop the --sop file from the corpus when it lives inside the inputs folder.

    It is fed to reconcile and synthesize as the SOP being revised, so extracting it as
    a raw document too would double-count every fact it already states. A SOP placed
    inside a subdirectory of inputs/ is not excluded — a subdirectory is one folder-level
    unit (see `ingest.load_corpus`), not individually addressable by file path.
    """
    if sop_path is None:
        return docs
    target = sop_path.resolve()
    return [d for d in docs if (d.path or inputs_dir / d.name).resolve() != target]


def run(
    inputs_dir: Path,
    out_dir: Path,
    schema_guide_path: Path,
    force_extract: bool = False,
    sop_path: Path | None = None,
    sop_name: str = "",
    sop_description: str = "",
) -> Path:
    """Full generation: inputs/ -> out/sop_generated.md (+ extraction + gap report).

    `sop_path`, when given, switches the run onto the revision route: the SOP at that path
    joins the pipeline at reconcile and synthesize as the document being revised, and its
    content is added to the gap-audit corpus so facts carried over from it are not flagged
    as hallucinations.

    `sop_name` and/or `sop_description`, when given (e.g. sop_name="PFML process"), scope
    the run to one SOP: statements are filtered down to that SOP before reconcile/synthesize
    see them (see `filter_by_sop`). With neither given, every extracted statement is used,
    unchanged. When `sop_name` is given, the output is written to `out/sop_<slug>.md`
    instead of `out/sop_generated.md`.
    """
    bar = _ProgressBar()
    out_dir.mkdir(parents=True, exist_ok=True)
    existing_sop = sop_path.read_text(encoding="utf-8") if sop_path else ""
    docs = _without_existing_sop(load_corpus(inputs_dir), inputs_dir, sop_path)
    audit_docs = docs + (
        [SourceDoc(sop_path.name, existing_sop)] if existing_sop else []
    )
    bar.log(f"Loaded {len(docs)} input file(s).")

    bar.log("========STATEMENT EXTRACTION========")
    statements = extract(
        docs, cache_dir=out_dir / "extraction_cache", force=force_extract, bar=bar
    )
    (out_dir / "extraction.json").write_text(
        json.dumps(statements, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if sop_name or sop_description:
        bar.log(f"Filtering statements for SOP: {(sop_name)!r}...")
        statements = filter_by_sop(
            statements,
            sop_name,
            sop_description,
            cache_dir=out_dir / "extraction_cache",
            force=force_extract,
        )
        (out_dir / "filtered_statements.json").write_text(
            json.dumps(statements, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        bar.log(f"  kept {len(statements)} statement(s) for {sop_name!r}.")

    bar.log("========SOP DRAFT GENERATION========")
    bar.log("Reconciling cross-file conflicts...")
    conflicts = reconcile(
        statements, cache_dir=out_dir, force=force_extract, existing_sop=existing_sop
    )
    (out_dir / "conflicts.json").write_text(
        json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bar.log(f"  found {len(conflicts)} cross-file conflict(s). ✅")

    bar.log("Synthesizing SOP...")
    schema_guide = schema_guide_path.read_text(encoding="utf-8")
    metadata = llm.document_metadata()
    if existing_sop:
        old_version = _extract_section1_field(existing_sop, "Version")
        if old_version:
            metadata = {**metadata, "version": _bump_version(old_version)}
    sop_md = synthesize(
        statements,
        schema_guide,
        conflicts=conflicts,
        metadata=metadata,
        existing_sop=existing_sop,
        existing_sop_name=sop_path.name if sop_path else "",
        new_input_names=[d.name for d in docs],
    )
    sop_filename = (
        f"sop_{_sop_name_slug(sop_name)}.md" if sop_name else "sop_generated.md"
    )
    sop_path = out_dir / sop_filename
    sop_path.write_text(sop_md + "\n", encoding="utf-8")
    bar.log("  SOP draft created ✅")
    bar.update(70)

    bar.log("========SOP REFINEMENT========")
    bar.log("Auditing for hallucinations / missing gaps...")
    report = gap_audit(sop_md, combined_corpus(audit_docs))
    report_path = out_dir / "audit_report.md"
    report_path.write_text(report + "\n", encoding="utf-8")
    bar.log(f"  audit report created at {report_path} ✅")

    bar.log("Revising SOP from audit findings...")
    sop_md = revise(sop_md, report)
    sop_md = _normalize_section1(sop_md, metadata)
    sop_path.write_text(sop_md + "\n", encoding="utf-8")
    bar.log("  revised SOP created ✅")
    bar.update(90)

    structural_warnings = (
        validate_gap_ids(sop_md)
        + validate_branches(sop_md)
        + validate_systems_coverage(sop_md, statements)
    )
    for warning in structural_warnings:
        bar.log(f"  WARNING: {warning}")

    bar.log("========ANNEX CREATION========")
    bar.log("Generating flow diagram...")
    mermaid_src, diagram_warnings = build_diagram(sop_md, out_dir, bar=bar)
    for warning in diagram_warnings:
        bar.log(f"  WARNING: {warning}")
    bar.log("  flow diagram generated ✅")

    # Persist the LLM audit + the deterministic validation warnings to one report. Written
    # here (not right after gap_audit) so the warnings computed above are included.
    gaps_md = (
        report + "\n" + _validation_warnings_md(structural_warnings, diagram_warnings)
    )
    (out_dir / "gaps_report.md").write_text(gaps_md + "\n", encoding="utf-8")
    # Drop any trailing separator/whitespace the SOP ends with so we add exactly one rule.
    body = sop_md.rstrip().rstrip("-").rstrip()
    # Keep the fenced block (renders on GitHub / Mermaid-aware viewers) and, when the CLI
    # produced an SVG, link it so Word/PDF readers see a picture rather than raw source.
    image_link = (
        "![SOP flow diagram](sop_flow_diagram.svg)\n\n"
        if (out_dir / "sop_flow_diagram.svg").is_file()
        else ""
    )
    annex = (
        f"\n\n---\n\n## Annex 1: Mermaid diagram\n\n"
        f"{_diagram_advisory(diagram_warnings)}"
        f"{image_link}```mermaid\n{mermaid_src}\n```\n"
    )
    (out_dir / "sop_flow_diagram.mmd").write_text(mermaid_src + "\n", encoding="utf-8")

    bar.log("Deriving cross-cutting invariants...")
    invariants_md = synthesize_invariants(sop_md)
    appendix = _appendix_a(_harvest_checkpoints(sop_md), invariants_md)
    bar.log("  invariants derived ✅")

    bar.log("Assembling front matter + Table of Contents...")
    front = _front_matter(sop_md, metadata)
    body_with_appendix = f"{body}{annex}\n\n---\n\n{appendix}\n"
    toc = _table_of_contents(body_with_appendix)
    final_sop = f"{front}\n\n---\n\n## Table of Contents\n\n{toc}\n\n---\n\n{body_with_appendix}"
    sop_path.write_text(final_sop, encoding="utf-8")

    bar.update(100)
    bar.log(f"Done -> {sop_path} ✅")
    bar.finish()
    return sop_path
