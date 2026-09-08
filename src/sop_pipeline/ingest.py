"""Read an inputs folder into a source-labeled corpus.

Supports .docx (python-docx), .md, .txt and .mp4 screen recordings. Every chunk keeps its
source filename so the SOP can state where each fact came from (a hard requirement of the
schema guide). A recording is recorded by path only — decoding and transcription happen in
the extract stage, so this module stays pure IO and a fully cached run touches neither
ffmpeg nor the API.

A subdirectory of the inputs folder is one *related document set* — a recording, its
transcript and notes from the same session — loaded as a single doc carrying its files as
`members`, so the extract stage can fuse them into one statement list.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VIDEO_SUFFIXES = {".mp4"}
SUPPORTED_SUFFIXES = {".docx", ".md", ".txt", ".markdown"} | VIDEO_SUFFIXES


@dataclass
class SourceDoc:
    """One input — a file or a folder of related documents — and its extracted text.

    `path` is set for videos, whose text is empty until the extract stage fills it with
    the audit corpus; it defaults to None so every existing call site keeps working.
    `members` is set only for a folder of related documents, whose text the extract stage
    fills from its members once their recordings have been extracted.
    """

    name: str
    text: str
    path: Path | None = None
    members: list[SourceDoc] | None = None

    def is_video(self) -> bool:
        """True for a recording, which the extract stage routes to the video branch.

        A folder is excluded on `members` rather than on its suffix, so a folder named
        "session.mp4" can never reach the video branch and hand a directory to ffmpeg.
        """
        return (
            self.members is None
            and self.path is not None
            and self.path.suffix.lower() in VIDEO_SUFFIXES
        )

    def is_folder(self) -> bool:
        """True for a folder of related documents, extracted as one unit."""
        return self.members is not None

    def labeled(self) -> str:
        """The document wrapped with an explicit source label for prompts."""
        return f"<<<SOURCE: {self.name}>>>\n{self.text.strip()}\n<<<END SOURCE>>>"


def _read_docx(path: Path) -> str:
    from docx import Document  # noqa: PLC0415 — local import: only needed for .docx

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_file(path: Path) -> SourceDoc | None:
    """One input file -> a SourceDoc, or None when unsupported or empty.

    A video legitimately carries no text at this point, so it escapes the empty-text drop.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return None
    if suffix in VIDEO_SUFFIXES:
        return SourceDoc(name=path.name, text="", path=path)
    text = _read_docx(path) if suffix == ".docx" else _read_text(path)
    return SourceDoc(name=path.name, text=text) if text.strip() else None


def _load_folder(directory: Path) -> SourceDoc | None:
    """A subdirectory -> ONE folder doc, or None when nothing in it is readable.

    Only files are collected, so a folder is always exactly one level deep. Member names are
    folder-qualified ("session_a/notes.md") so a statement's source and a recording's cache
    entry stay unique across folders. `text` stays empty here — this module is pure IO;
    `pipeline._extract_folder` fills it once the member recordings have been extracted.
    """
    members: list[SourceDoc] = []
    for path in sorted(directory.iterdir()):
        if path.name.startswith("."):
            continue
        if not path.is_file():
            print(
                f"  WARNING: ignoring {path} — a related document set is exactly one "
                f"level deep, so nothing nested inside it is read"
            )
            continue
        member = _load_file(path)
        if member is not None:
            member.name = f"{directory.name}/{member.name}"
            members.append(member)
    if not members:
        return None
    return SourceDoc(name=directory.name, text="", path=directory, members=members)


def load_corpus(inputs_dir: Path) -> list[SourceDoc]:
    """Load every supported file in inputs_dir, sorted by name for determinism.

    A subdirectory yields one folder doc holding its files as members
    """
    if not inputs_dir.is_dir():
        raise FileNotFoundError(f"Inputs directory not found: {inputs_dir}")

    docs: list[SourceDoc] = []
    for path in sorted(inputs_dir.iterdir()):
        if path.name.startswith("."):
            continue
        entry = _load_folder(path) if path.is_dir() else _load_file(path)
        if entry is not None:
            docs.append(entry)

    if not docs:
        raise ValueError(
            f"No readable inputs in {inputs_dir} "
            f"(supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}; "
            f"{', '.join(sorted(VIDEO_SUFFIXES))} files are accepted with no text of "
            f"their own)."
        )
    return docs


def combined_corpus(docs: list[SourceDoc]) -> str:
    """All documents concatenated with source labels, for whole-corpus prompts."""
    return "\n\n".join(doc.labeled() for doc in docs)
