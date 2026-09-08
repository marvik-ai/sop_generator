"""ffmpeg scaffolding: sample a recording's frames, split its audio into chunks.

The ffmpeg binary comes from imageio-ffmpeg (a pyproject.toml dependency) — no system
ffmpeg install is required.
"""

import re
import subprocess  # noqa: S404 - ffmpeg is a trusted local tool, args are not user shell
from pathlib import Path

import imageio_ffmpeg


# Decoding a long screen recording takes minutes of CPU, so the timeout is generous.
_TIMEOUT_S = 900

_MISSING_FFMPEG = (
    "ffmpeg is required to read video inputs but imageio-ffmpeg has no binary for this "
    "platform. Reinstall imageio-ffmpeg (`uv sync`)"
)

# ffmpeg prints e.g. "Duration: 00:04:12.34, start: ..." to stderr while probing.
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")


def _ffmpeg_command() -> list[str] | None:
    """Return the ffmpeg invocation to use, or None if the bundled binary is unavailable."""
    try:
        return [imageio_ffmpeg.get_ffmpeg_exe()]
    except (OSError, RuntimeError):
        # Raises when the wheel has no binary for this platform (e.g. a source install).
        return None


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a fixed local tool, normalizing "could not run at all" into a failed result."""
    try:
        return subprocess.run(  # noqa: S603 - command is a fixed local tool, no shell
            argv, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
        )
    except (subprocess.TimeoutExpired, OSError) as err:
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr=str(err))


def _error_text(proc: subprocess.CompletedProcess[str]) -> str:
    """The tail of ffmpeg's output — it prints its whole build banner before the error."""
    text = (proc.stderr or proc.stdout or "ffmpeg failed with no output").strip()
    return "\n".join(text.splitlines()[-10:])


def _extract(
    argv: list[str], out_dir: Path, pattern: str, label: str, path: Path
) -> list[Path]:
    """Purge `out_dir`, run one ffmpeg pass, and return the numbered files it writes, sorted by name.

    Purging first keeps a shorter rerun from mixing leftover files from a previous run into its output.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(pattern):
        stale.unlink(missing_ok=True)

    proc = _run(argv)
    written = sorted(out_dir.glob(pattern))
    if proc.returncode != 0 or not written:
        raise RuntimeError(
            f"ffmpeg failed to extract {label} from {path.name}: {_error_text(proc)}"
        )
    return written


def extract_frames(
    path: Path, out_dir: Path, *, interval_s: float, width: int
) -> list[Path]:
    """Sample `path` to JPEG frames in `out_dir`, one every `interval_s` seconds.

    `fps=1/interval` samples the frames and `scale=width:-2` resizes them, keeping an even,
    aspect-correct height. `-q:v 4` keeps CUSTOM_SYSTEM field labels legible. The nth frame lands
    at (n-1) * interval, so the caller derives every timestamp from the returned order.
    """
    command = _ffmpeg_command()
    if command is None:
        raise RuntimeError(_MISSING_FFMPEG)
    argv = [
        *command,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(path),
        "-vf",
        f"fps=1/{interval_s},scale={width}:-2",
        "-q:v",
        "4",
        str(out_dir / "frame_%05d.jpg"),
    ]
    return _extract(argv, out_dir, "frame_*.jpg", "frames", path)


def extract_audio(path: Path, out_dir: Path, *, chunk_s: float) -> list[Path]:
    """Split `path`'s audio track into fixed-length mono AAC chunks ready for ASR.

    AAC is a built-in ffmpeg encoder and `.m4a` is an accepted Whisper input. Mono 16 kHz
    keeps a chunk well under Whisper's 25 MB upload limit. `-reset_timestamps 1` resets
    each chunk's clock to zero, so the caller shifts its segments by `index * chunk_s`.
    """
    command = _ffmpeg_command()
    if command is None:
        raise RuntimeError(_MISSING_FFMPEG)
    argv = [
        *command,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_s),
        "-reset_timestamps",
        "1",
        str(out_dir / "audio_%05d.m4a"),
    ]
    return _extract(argv, out_dir, "audio_*.m4a", "audio", path)


def probe_duration(path: Path) -> float:
    """`path`'s duration in seconds, read from ffmpeg's own stderr.

    imageio-ffmpeg bundles only `ffmpeg`, not `ffprobe`. `-f null -` gives ffmpeg an
    output target so it actually decodes (and so reliably flushes the
    `Duration: HH:MM:SS.xx` line to stderr) instead of possibly exiting before that line
    is written.
    """
    command = _ffmpeg_command()
    if command is None:
        raise RuntimeError(_MISSING_FFMPEG)
    argv = [*command, "-hide_banner", "-nostdin", "-i", str(path), "-f", "null", "-"]
    proc = _run(argv)
    match = _DURATION_RE.search(proc.stderr or "")
    if match is None:
        raise RuntimeError(
            f"ffmpeg did not report a duration for {path.name}: {_error_text(proc)}"
        )
    hours, minutes, seconds, fraction = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + float(f"0.{fraction}")
