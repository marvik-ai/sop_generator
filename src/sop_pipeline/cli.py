"""CLI: generate-mocks | run | evaluate."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import mocks, pipeline


ROOT = Path(__file__).resolve().parents[2]  # sop_pipeline/
INPUTS = ROOT / "inputs"
OUT = ROOT / "out"
MANIFEST = ROOT / "fixtures" / "coverage_manifest.md"


def _cmd_generate_mocks(args: argparse.Namespace) -> None:
    print("Generating mock inputs from the north-star SOP...")
    mocks.generate(Path(args.north_star), Path(args.inputs), Path(args.manifest))
    print(f"Done. Review {args.inputs} and {args.manifest}.")


def _cmd_run(args: argparse.Namespace) -> None:
    schema_guide_path = Path(args.schema_guide)
    if not schema_guide_path.is_file():
        raise SystemExit(f"Schema guide not found: {schema_guide_path}")
    pipeline.run(
        Path(args.inputs),
        Path(args.out),
        schema_guide_path,
        force_extract=args.force_extract,
    )


def _cmd_evaluate(args: argparse.Namespace) -> None:
    sop_path = Path(args.sop)
    if not sop_path.is_file():
        raise SystemExit(f"Generated SOP not found: {sop_path}. Run `run` first.")
    north_star = Path(args.north_star)
    manifest = Path(args.manifest)
    report = pipeline.evaluate(
        sop_path.read_text(encoding="utf-8"),
        north_star.read_text(encoding="utf-8"),
        manifest.read_text(encoding="utf-8") if manifest.is_file() else "(no manifest)",
    )
    out_path = Path(args.out) / "evaluation.md"
    out_path.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nWritten to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="sop-pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_mocks = sub.add_parser(
        "generate-mocks", help="reverse-engineer mock inputs from the north-star SOP"
    )
    p_mocks.add_argument("--inputs", default=str(INPUTS))
    p_mocks.add_argument(
        "--north-star", required=True, help="path to the trusted north-star SOP (not tracked in the repo)"
    )
    p_mocks.add_argument("--manifest", default=str(MANIFEST))
    p_mocks.set_defaults(func=_cmd_generate_mocks)

    p_run = sub.add_parser("run", help="generate an SOP from a folder of inputs")
    p_run.add_argument("--inputs", default=str(INPUTS))
    p_run.add_argument("--out", default=str(OUT))
    p_run.add_argument(
        "--schema-guide",
        required=True,
        help="path to the SOP schema guide (11-section template the generator must follow)",
    )
    p_run.add_argument(
        "--force-extract",
        action="store_true",
        help="bypass the extraction cache and re-extract every file",
    )
    p_run.set_defaults(func=_cmd_run)

    p_eval = sub.add_parser(
        "evaluate", help="score the generated SOP against the north star"
    )
    p_eval.add_argument("--sop", default=str(OUT / "sop_generated.md"))
    p_eval.add_argument("--out", default=str(OUT))
    p_eval.add_argument(
        "--north-star", required=True, help="path to the trusted north-star SOP (not tracked in the repo)"
    )
    p_eval.add_argument("--manifest", default=str(MANIFEST))
    p_eval.set_defaults(func=_cmd_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
