"""Video inputs: turns an .mp4 into the statement list extracted from it.

Two independent config keys pick two independent axes: `config.yaml`'s `frame_extraction`
key picks HOW frames are sampled from the recording, and `strategy` picks HOW the sampled
frames are turned into statements. Callers outside this package use only the three
functions below. See README.md in this folder for what each option does. Point
`SOP_VIDEO_CONFIG` at a YAML file to override `config.yaml` keys without editing it.

An analysis-strategy module implements:
    extract(path: Path, knobs: dict) -> list[dict]   statements pulled from one recording
    cache_key(knobs: dict) -> str                     strategy name + knobs that change the output
    prompt_name() -> str                              the prompt file it renders

`knobs` is the merged `shared:` + the active `frame_extraction` strategy's own section +
the active analysis strategy's own section, plus the active `frame_extraction` name
itself (so a strategy's `cache_key` sees, and can invalidate on, everything that changes
the frames it's handed).
"""

import os
from pathlib import Path
from types import ModuleType

import yaml

from sop_pipeline.video import frame_extraction, naive, sequential


_CONFIG_FILE = Path(__file__).parent / "config.yaml"
_CUSTOM_CONFIG_ENV_VAR = "SOP_VIDEO_CONFIG"

_STRATEGIES: dict[str, ModuleType] = {
    naive.STRATEGY_NAME: naive,
    sequential.STRATEGY_NAME: sequential,
}


def _deep_merge(base: dict, override: dict) -> dict:
    """`override` layered onto `base`, merging nested dicts key-by-key so a custom config
    only needs to state the keys it changes.
    """
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _config() -> dict:
    """The merged video config: `config.yaml` overlaid with the file at `SOP_VIDEO_CONFIG`, if set.

    Re-read on every call, so an edited custom config or a monkeypatched value takes
    effect immediately.
    """
    config = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8"))
    custom_path = os.environ.get(_CUSTOM_CONFIG_ENV_VAR)
    if custom_path:
        custom_file = Path(custom_path)
        if not custom_file.is_file():
            raise RuntimeError(
                f"{_CUSTOM_CONFIG_ENV_VAR}={custom_path!r} does not point to a file."
            )
        custom = yaml.safe_load(custom_file.read_text(encoding="utf-8")) or {}
        config = _deep_merge(config, custom)
    return config


def _active() -> tuple[ModuleType, dict]:
    """The selected analysis-strategy module and its resolved knobs (shared + the active
    frame-extraction strategy's own knobs + this strategy's own knobs + the
    frame-extraction strategy's name).

    Resolved on every call, so a `SOP_VIDEO_CONFIG` override takes effect immediately.
    Raises on an unknown strategy (either axis) so a typo fails fast instead of running
    silently against the wrong strategy.
    """
    config = _config()
    name = str(config["strategy"]).strip()
    strategy = _STRATEGIES.get(name)
    if strategy is None:
        valid = ", ".join(sorted(_STRATEGIES))
        raise RuntimeError(
            f"Unknown strategy {name!r} in config.yaml. Valid strategies: {valid}."
        )

    frame_name = str(config["frame_extraction"]).strip()
    if frame_name not in frame_extraction._STRATEGIES:
        valid = ", ".join(sorted(frame_extraction._STRATEGIES))
        raise RuntimeError(
            f"Unknown frame_extraction strategy {frame_name!r} in config.yaml. "
            f"Valid: {valid}."
        )

    # Last write wins: the frame_extraction NAME itself is folded in so switching it
    # invalidates a strategy's cache_key even if, by coincidence, every knob VALUE
    # happens to match the previous frame-extraction strategy's.
    knobs = {
        **(config.get("shared") or {}),
        **(config.get(frame_name) or {}),
        **(config.get(name) or {}),
        "frame_extraction": frame_name,
    }
    return strategy, knobs


def strategy_name() -> str:
    return str(_config()["strategy"]).strip()


def frame_extraction_name() -> str:
    return str(_config()["frame_extraction"]).strip()


def _strategy() -> ModuleType:
    """The selected strategy module (see the fail-fast note in `_active`)."""
    strategy, _ = _active()
    return strategy


def extract(path: Path) -> list[dict]:
    """Statements from one recording, using the selected strategy."""
    strategy, knobs = _active()
    return strategy.extract(path, knobs)


def cache_key() -> str:
    """The selected strategy's cache key (see the strategy contract above)."""
    strategy, knobs = _active()
    return strategy.cache_key(knobs)


def prompt_name() -> str:
    """The prompt file the selected strategy renders."""
    return _strategy().PROMPT_NAME


__all__ = [
    "cache_key",
    "extract",
    "frame_extraction_name",
    "prompt_name",
    "strategy_name",
]
