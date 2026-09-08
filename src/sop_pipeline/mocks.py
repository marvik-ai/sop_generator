"""Reverse-engineer a varied set of mock inputs from the north-star SOP.

The *specs* below are the ground truth: each one dictates exactly what its file must
cover and must omit, so the coverage manifest we write is reliable (defined by us, not
inferred from whatever the model produced). The model only renders each spec into a
realistic transcript/document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import llm
from .prompts import load_prompt, render


@dataclass
class MockSpec:
    filename: str
    kind: str  # "transcript" | "document"
    profile: str  # short human label, e.g. "clean overview"
    personas: str  # who speaks / authored it (non-native English speakers vary)
    noise_level: str  # none | low | medium | high
    error_level: str  # none | low | medium | high  (spelling / ASR errors)
    must_include: list[str]  # facts/sections this file MUST carry
    must_omit: list[str]  # facts this file must NOT mention (tested as gaps elsewhere)
    contradicts: str = ""  # description of any deliberate contradiction
    unique: str = ""  # facts found ONLY in this file (tests cross-file synthesis)
    extra: str = ""  # any extra rendering guidance


# The set: clean + noisy + distributed + spelling errors + a contradiction + docs,
# all in English spoken by a mix of American / Indian / Argentinean people.
SPECS: list[MockSpec] = [
    MockSpec(
        filename="transcript_01_clean_overview.md",
        kind="transcript",
        profile="clean, near-complete walkthrough",
        personas="Sandra (American, facilitator) and Ranjit (Indian, principal architect) walking Marvik through the process",
        noise_level="low",
        error_level="none",
        must_include=[
            "Purpose & scope of standalone unpaid absence (job protection vs income protection)",
            "Glossary: leave plan, applicability, certified period, PLAN_TIER, CUSTOM_SYSTEM",
            "Systems: CUSTOM_SYSTEM as system of record; a rules database holding business rules",
            "The end-to-end flow: intake -> applicability -> eligibility -> availability -> evidence -> restrictions -> final decision",
            "The terminal end-states (approved & closed, excluded/logged, routed to manual, technical error)",
        ],
        must_omit=[
            "The exact pilot customer list",
            "Exact numeric thresholds for restriction overrides",
            "Exact field-level UI screens used when no API path exists",
        ],
        unique="The full ordered narrative of all six gates and the catalog of end-states.",
    ),
    MockSpec(
        filename="transcript_02_noisy_intake.md",
        kind="transcript",
        profile="noisy meeting focused on intake",
        personas="Mike (American, ops lead) and Pablo (Argentinean, developer), lots of meeting-join chatter",
        noise_level="high",
        error_level="low",
        must_include=[
            "Intake & routing step: what triggers the process",
            "Two entry sources: (1) new claim created in CUSTOM_SYSTEM, (2) new evidence uploaded to an existing claim",
            "That only customers on an active pilot list are handled (but NOT which customers)",
        ],
        must_omit=[
            "Eligibility, availability, evidence, restrictions and decision logic (covered elsewhere)",
            "Exact pilot customer list",
        ],
        unique="The evidence-upload entry source as a distinct trigger.",
        extra="Open with Teams join noise ('can you see my screen?', 'you're on mute', crosstalk) and screen-share narration before getting to substance.",
    ),
    MockSpec(
        filename="doc_01_functional_overview.md",
        kind="document",
        profile="semi-structured functional overview doc",
        personas="authored as an internal company functional overview (no speakers)",
        noise_level="none",
        error_level="none",
        must_include=[
            "In-scope table: standalone UNPAID absence only; single leave request; no-extension claims this phase",
            "Out-of-scope exclusions WITH reasons: combined absence+STD, extension claims, multiple leave requests",
            "Systems table: CUSTOM_SYSTEM (system of record), rules database, operational UI automation",
        ],
        must_omit=[
            "Step-level IF/THEN decision logic (covered in transcripts)",
            "Numeric thresholds",
        ],
        unique="The explicit out-of-scope exclusion list with the reason for each.",
        extra="Render as a real doc with headings and tables, slightly incomplete (a couple of 'TBD' cells).",
    ),
    MockSpec(
        filename="doc_02_rules_sheet_partial.md",
        kind="document",
        profile="partial business-rules sheet",
        personas="authored as a partial rules reference extract (no speakers)",
        noise_level="none",
        error_level="low",
        must_include=[
            "Rule: only DURATION-LIMIT restrictions may be auto-overridden; all other restriction types are out of scope",
            "Rule: pilot-customer gating (process only runs for customers on the pilot list)",
            "A SPECIFIC threshold: duration-limit may be auto-extended by up to 5 days",
            "Several rules explicitly marked 'TBD — see customer Spreadsheet' (opaque rules)",
        ],
        must_omit=[
            "The actual pilot customer names",
            "Applicability value-mapping internals",
        ],
        contradicts="States the duration-limit auto-extension threshold is 5 days; transcript_04 says 10 days.",
        unique="Concrete rule IDs and the 5-day threshold value.",
        extra="Render as a partial table; leave clearly-marked TBD/opaque entries.",
    ),
    MockSpec(
        filename="transcript_03_eligibility_spelling.md",
        kind="transcript",
        profile="eligibility logic, heavy transcription errors",
        personas="Neeraj (Indian, SME) and Karen (American, analyst); auto-transcribed with many ASR errors",
        noise_level="medium",
        error_level="high",
        must_include=[
            "Eligibility evaluation step with IF/THEN logic (e.g. tenure / hours / coverage conditions)",
            "Availability evaluation step (entitlement balance remaining for the leave plan)",
            "How a failing eligibility/availability check routes the claim to manual adjudication",
        ],
        must_omit=[
            "Evidence and restrictions steps",
            "Exact opaque rule mappings in the rules database",
        ],
        unique="The eligibility and availability decision branches and their manual-routing exits.",
        extra="Mangle system/term names as ASR would: CUSTOM_SYSTEM -> 'Custom System/Sistem', FMLA -> 'F M L A/effemela', PLAN_TIER -> 'plan tier/plantier', certified -> 'certify'. Keep it understandable but visibly noisy.",
    ),
    MockSpec(
        filename="transcript_04_restrictions_contradiction.md",
        kind="transcript",
        profile="restrictions + final decision, with a contradiction",
        personas="Sandra (American, facilitator) and Facundo (Argentinean, delivery lead)",
        noise_level="medium",
        error_level="low",
        must_include=[
            "Restrictions step: only duration-limit restrictions are auto-overridden",
            "Final decision step: certify approved periods in CUSTOM_SYSTEM and advance the leave request",
            "What gets recorded for each end-state (notes/tasks/statuses)",
        ],
        must_omit=[
            "Exact UI field names used for the certification screen",
        ],
        contradicts="Asserts the duration-limit auto-extension threshold is 10 days, contradicting doc_02's 5 days.",
        unique="The certification/advance actions and the per-end-state recorded artifacts.",
        extra="Include a moment where a speaker is unsure of the exact threshold ('I think it's ten days, but check the spreadsheet').",
    ),
]


# Facts that NO input provides on purpose — the pipeline should surface these as gaps.
GLOBALLY_OMITTED = [
    "The exact pilot customer list (MISSING-DETAIL / will become a gap).",
    "The precise applicability value-to-bucket mapping held in the rules database (OPAQUE-RULE).",
    "The exact UI screens/fields used when no programmatic path exists (MISSING-DETAIL).",
    "The duration-limit auto-extension threshold is CONTRADICTED across inputs (5 vs 10 days) -> AMBIGUITY.",
]


def generate(north_star_path: Path, inputs_dir: Path, manifest_path: Path) -> None:
    """Render every spec into inputs/ and write the coverage manifest from the specs."""
    north_star = north_star_path.read_text(encoding="utf-8")
    template = load_prompt("01_generate_mocks.md")
    inputs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    for spec in SPECS:
        prompt = render(
            template,
            NORTH_STAR=north_star,
            FILENAME=spec.filename,
            KIND=spec.kind,
            PROFILE=spec.profile,
            PERSONAS=spec.personas,
            NOISE_LEVEL=spec.noise_level,
            ERROR_LEVEL=spec.error_level,
            MUST_INCLUDE="\n".join(f"- {x}" for x in spec.must_include),
            MUST_OMIT="\n".join(f"- {x}" for x in spec.must_omit),
            CONTRADICTS=spec.contradicts or "(none)",
            EXTRA=spec.extra or "(none)",
        )
        body = llm.complete(prompt, model=llm.synth_model(), max_tokens=8000)
        (inputs_dir / spec.filename).write_text(body.strip() + "\n", encoding="utf-8")
        print(f"  wrote inputs/{spec.filename}")

    manifest_path.write_text(_render_manifest(), encoding="utf-8")
    print(f"  wrote {manifest_path}")


def _render_manifest() -> str:
    lines = [
        "# Coverage Manifest (ground truth for the mock input set)",
        "",
        "Authored from the mock specs, not inferred from generated content. Use this to",
        "grade the pipeline: every 'omitted globally' item should surface as a typed gap",
        "in the generated SOP's Section 10, and nothing outside these inputs should be",
        "asserted as fact.",
        "",
        "## Per-file coverage",
        "",
    ]
    for spec in SPECS:
        lines += [
            f"### `{spec.filename}` — {spec.profile}",
            f"- **Kind:** {spec.kind}",
            f"- **Personas:** {spec.personas}",
            f"- **Noise / error level:** {spec.noise_level} / {spec.error_level}",
            "- **Covers:**",
            *[f"    - {x}" for x in spec.must_include],
            "- **Deliberately omits:**",
            *[f"    - {x}" for x in spec.must_omit],
        ]
        if spec.contradicts:
            lines.append(f"- **Contradiction:** {spec.contradicts}")
        if spec.unique:
            lines.append(f"- **Unique to this file:** {spec.unique}")
        lines.append("")

    lines += [
        "## Omitted across ALL inputs (must appear as gaps in the SOP)",
        "",
        *[f"- {x}" for x in GLOBALLY_OMITTED],
        "",
    ]
    return "\n".join(lines)
