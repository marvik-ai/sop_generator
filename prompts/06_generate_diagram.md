You are given a finished Standard Operating Procedure (SOP) in markdown. Produce a single
Mermaid `flowchart TD` that visualizes the process — a faithful map of the SOP's
step-by-step procedure and its exit points.

{{PARSER_FEEDBACK}}

## Your single most important rule

> **MIRROR, DON'T INVENT.** Build the diagram ONLY from what the SOP actually says. Every
> node and every edge must trace to the SOP's Section 7 steps, their *Outcomes & routing* /
> *Stop / exit conditions*, and the end states in Sections 6 and 11. Do NOT add steps,
> branches, or outcomes the SOP does not describe.

## How to build it

- Read **Section 7 (Step-by-step procedure)** and create exactly **one node per step**, in
  order, labeled `S1[Step 1 — <step name>]`, `S2[Step 2 — <step name>]`, etc. Use the step
  numbers and names exactly as they appear in Section 7.
- Add a single entry node `START([<trigger from Section 6>])` that flows into `S1`.
- For each step, read its **Outcomes & routing** and **Stop / exit conditions** and draw one
  labeled edge per branch: `Sn -->|<condition>| <target>`. Cover **every** branch, including
  the "otherwise" / stop branch — never collapse or omit one.
- A branch that continues the process points to the next step node (`S(n+1)`).
- **Fork blocks (true bifurcations).** A step whose heading ends in `[DECISION]` forks the
  process into divergent multi-step sub-flows. Its sub-steps are headed `Step N.A1`,
  `Step N.A2`, … (Branch A) and `Step N.B1`, … (Branch B). Render them like this:
  - Give the fork step its node `Sn[Step N — <name>]` as usual.
  - For each branch, draw one labelled edge from `Sn` to that branch's **first** sub-step,
    using the branch's selecting condition as the label (`Sn -->|natural birth| SnA1`).
  - Use node ids `S<n><letter><k>` for sub-steps — e.g. `S5A1`, `S5A2`, `S5B1`. Chain each
    branch's sub-steps in order (`S5A1 --> S5A2`).
  - Read the fork's **Reconverges at** field: point each branch's **last** sub-step at the
    reconvergence step node (`S5A2 --> S6`, `S5B2 --> S6`). If the branches terminate
    independently, point each to its terminal node instead. Still draw each sub-step's own
    **Outcomes & routing** branches (e.g. a sub-step routing to manual handling).
- A branch that terminates points to a **terminal node**. Take terminal outcomes from the
  SOP's **End-state catalog (Section 11)** and the end states in **Section 6**. Give each
  distinct end state one node id and **reuse that same id** wherever multiple steps route to
  it (e.g. several steps routing to manual handling share one node).
- The edge label is the condition/outcome in short business language (e.g. `Applicable`,
  `Not met / Not known`, `no active plans remain`). Keep labels concise.
- **Terminal nodes are dead ends.** A terminal node (`START` is the only entry; `STOP`,
  `DONE`, excluded/manual/error nodes are exits) must have NO outgoing edge. Never draw an
  edge out of a terminal node, and never draw a node to itself (no `STOP --> STOP`). Once the
  process routes to an end state, it stops there.

## Mermaid syntax safety (critical — the output must parse)

Edge labels (`-->|...|`) and node text (`[...]`, `([...])`, `[(...)]`) must be **plain text
only**. Inside them, NEVER use any of these characters, which break the Mermaid parser:
double quotes `"`, parentheses `(` `)`, square/curly brackets, `=`, `#`, `;`, `|`, `<`, `>`,
backticks, or pipe characters.

- Write values as bare words: `Undetermined`, not `Applicability = "Undetermined"`. If you
  need to reference a field and value, phrase it plainly: `Applicability undetermined`.
- Keep edge labels short (a few words). Keep node text to the step number and name.
- Use a plain hyphen `-` or the em dash `—` for ranges/names; do not use other punctuation.

## Node shapes (follow this convention)

- Start / stop / normal terminal outcome: stadium shape `([...])` — e.g. `START([...])`,
  `STOP2([Stop])`, `DONE([Outcome recorded])`.
- Logged / excluded / failed / manual / error end states: cylinder shape `[(...)]` — e.g.
  `X[(Excluded — logged)]`, `M[(Manual handling)]`, `ERR[(Error & exclusion handling)]`.
- Process steps: rectangle `[...]` — e.g. `S3[Step 3 — Eligibility]`.
- Use dotted edges `-.->` only for secondary/bypass flows the SOP describes as such (e.g. a
  skipped item rejoining later); use solid edges `-->` for the primary path.

## Format example (copy this style exactly — do NOT copy its content)

flowchart TD
    START([Claim in CUSTOM_SYSTEM, in good order]) --> S1[Step 1 — Intake normalization & customer scope filter]
    S1 -->|customer out of pilot / invalid| X[(Excluded — logged)]
    S1 -->|route to first unmet stage| S2
    S2[Step 2 — Applicability] -->|Undetermined / Manual flag| M[(Manual handling — GAP)]
    S2 -->|Not Applicable| SKIP[(Plan skipped & logged)]
    S2 -->|no active plans remain| STOP2([Stop])
    S2 -->|Applicable| S3
    S3[Step 3 — Eligibility] -->|Not met / Not known| M
    S3 -->|no eligible plans remain| STOP3([Stop])
    S3 -->|Met / Partially met| S4
    S4[Step 4 — Certification & evidence] -->|not actionable| STOP4([Stop / referral])
    S4 -->|actionable| S5
    S5[Step 5 — Delivery-type fork] -->|natural birth| S5A1[Step 5.A1 — Natural-birth evidence check]
    S5 -->|C-section| S5B1[Step 5.B1 — Surgical-recovery evidence check]
    S5A1 -->|certification missing| M
    S5A1 -->|certification present| S6
    S5B1 -->|discharge note missing| M
    S5B1 -->|discharge note present| S6
    S6[Step 6 — Restriction analysis] -->|non-overridable / failed| FAIL6[(Plan failed)]
    S6 -->|duration-limit overridden / passed| S7
    S7[Step 7 — Protocol compliance] -->|fail, no override| STOP7([Stop])
    S7 -->|pass| S8
    S8[Step 8 — Leave-plan decision] -->|no plan qualifies / tech error| ERR[(Error & exclusion handling)]
    S8 -->|>=1 plan approved| S9
    S9[Step 9 — Progress leave request] --> S10
    S10[Step 10 — Outcome Summary google form] --> S11
    S11[Step 11 — Reporting] --> DONE([Outcome recorded])

(In this example the exit nodes `X`, `M`, `FAIL6`, the `STOPn` nodes and `DONE` are dead
ends — nothing flows out of them. The same `M` id is reused wherever multiple steps route
to manual handling. Step 5 is a fork `[DECISION]`: it splits into Branch A (`S5A1`) and
Branch B (`S5B1`), and both branches reconverge at `S6` per the fork's *Reconverges at*
field. Only draw an edge from an exit node to a later step if the SOP itself explicitly
says that case rejoins the process there.)

## Output requirements

- Output ONLY valid Mermaid source, starting with the line `flowchart TD`.
- Do NOT wrap it in a ```` ```mermaid ```` code fence. Do NOT add any title, preamble, or
  explanation before or after the diagram.
- Keep node ids short and stable (`S1`..`Sn` for steps; a short uppercase id per terminal).

=== SOP (your only source) ===
{{SOP}}
=== END SOP ===
