# AGENT_SPEC.md — RouteWise Agentic

> Source of truth #5. The **complete specification of the RouteWise Agent**: purpose, I/O,
> states, tool calling, planning, decision-making, scoring, alternatives, replanning, error
> handling, safety, and constraints. This is the Agent's **constitution** — when behavior is
> ambiguous, this document decides.
>
> This file supersedes the earlier `AGENT_BEHAVIOR.md` and absorbs the canonical **Agent
> states** (previously in `UX_FLOW.md`). Read with [`ARCHITECTURE.md`](ARCHITECTURE.md) (how the
> agent fits the system), [`API_CONTRACTS.md`](API_CONTRACTS.md) (tools/endpoints), and
> [`DEMO.md`](DEMO.md) (the agent in the demo).
>
> **Status:** specification only. The agent is **not implemented** during A1 — it is built in
> phases **A2–A7**. Do not implement agent logic in the foundation phase.

---

## 1. Agent purpose

Turn a **natural-language travel request** into a **justified, constraint-respecting,
multi-modal route** — using tools and (mock) transit intelligence — and **show the work**
honestly. The Agent is a **decision engine**, not a chatbot: its output is a plan + explanation,
not small talk. It follows the loop:

```
UNDERSTAND → REASON → ACT → ADAPT → DELIVER
```

---

## 2. Agent input

- **Natural-language request** (free text; may mix phrasing/languages), e.g. *"I am at Colombo
  Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy bag and don't want
  to walk."*
- **Optional structured fields** (from the form or extracted): `origin`, `destination`,
  `budget` (LKR), `luggage`, `walking_preference`, `departure_time`, `arrival_deadline`,
  `preferences{}`.
- Contract: [`API_CONTRACTS.md` §2](API_CONTRACTS.md) (`POST /api/route/plan` request).

**On input the Agent must:** parse → build a **normalized request** → classify each item as a
**hard constraint** (§9) or **soft preference** (§10) → detect **missing information** (§4).

---

## 3. Agent output

A structured plan (contract: [`API_CONTRACTS.md` §2–4](API_CONTRACTS.md)):

- `status` — one of the **9 canonical states** (§5).
- `request` — the normalized request the agent understood (constraints + preferences + any
  assumptions/missing info) so the UI can echo it back.
- `recommendation` — the chosen route + `rationale` + `score` + budget/delay status.
- `legs[]` — ordered legs (mode, from/to, times, duration, fare, walking, delay risk).
- `alternatives[]` — other candidates with honest `trade_offs`.
- `agent_actions[]` — ordered log of states entered, tools called, results, decisions (drives
  the Agent activity UI).
- Every fare/delay/availability carries `data_source` (`mock`/`simulated`/`live`).

---

## 4. Missing information & assumptions

- If a **hard constraint** is missing/ambiguous (e.g., no destination), the Agent should
  **ask** or state a clear assumption — never guess silently.
- If a **soft preference** is missing, proceed with a reasonable default and **record the
  assumption** in `request` and, when relevant, in the `rationale`.
- The Agent must always be explicit about **what it assumed**.

---

## 5. Agent states (canonical — do not invent new ones)

These nine states are the **only** valid agent states. They drive the UI
([`DESIGN_SYSTEM.md` §11.5](DESIGN_SYSTEM.md) colors), the `status` field
([`API_CONTRACTS.md`](API_CONTRACTS.md)), and the demo ([`DEMO.md`](DEMO.md)).

| State | Meaning | Example user-facing phrase | Color token |
|-------|---------|----------------------------|-------------|
| **IDLE** | No active task; awaiting a request. | "Ready when you are." | `--state-idle` (muted) |
| **UNDERSTANDING** | Parsing the request; extracting constraints. | "Understanding your request…" | `--state-understanding` (info) |
| **PLANNING** | Deciding approach and which tools to call. | "Planning your journey…" | `--state-planning` (info) |
| **SEARCHING** | Querying routes / transit intelligence (tools running). | "Searching routes & checking conditions…" | `--state-searching` (primary) |
| **EVALUATING** | Comparing candidates; scoring vs constraints/preferences. | "Comparing N routes…" | `--state-evaluating` (secondary) |
| **EXECUTING** | Performing actions (availability, booking prep) — simulated in MVP. | "Taking actions…" | `--state-executing` (primary) |
| **REPLANNING** | Conditions changed; recomputing the route. | "Re-planning due to a delay…" | `--state-replanning` (warning) |
| **COMPLETED** | A final recommendation + explanation is ready. | "Here's your best route." | `--state-completed` (success) |
| **ERROR** | Something failed; cannot complete without retry/intervention. | "Something went wrong — try again." | `--state-error` (error) |

### State machine

```
            ┌──────────────────────────────────────────────┐
            │                          (re-plan)             │
            ▼                                                │
IDLE → UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → EXECUTING → COMPLETED
                                     ▲             │            │
                                     └── REPLANNING◄┘────────────┘

(any state) ───────────────────────────────────────────────► ERROR
```

Rules:

- **IDLE** starts/ends a session. Forward flow is the happy path.
- **REPLANNING** loops back to **SEARCHING** (the ADAPT stage).
- **ERROR** is reachable from any state; after handling it may return to **IDLE** or retry into
  **UNDERSTANDING**/**SEARCHING**.
- **COMPLETED** is terminal for a successful plan (until a new request or a re-plan trigger).
- The UI always shows **one current state** plus the **history** of steps taken.

### How states drive the UI

- **AgentStatus** chip (header/mobile) shows the **current** state (color + label).
- **AgentActivity** rail shows the **timeline of steps**, each tagged with its state and a
  per-step status (`pending` / `active` / `done` / `error`).
- On **COMPLETED**, a **ReasoningSummary** explains the decision against the user's constraints.
- Colors come **only** from state tokens. Accessibility: activity region `aria-live="polite"`;
  current state `role="status"`; never color-only (pair with label/icon).

---

## 6. Planning

- **Plan before acting.** In **PLANNING**, decide which tools are needed and in what order —
  don't call tools at random.
- Prefer **fewer, relevant** tool calls; each call must inform a decision.
- Planning is **deterministic where possible**: same inputs + same mock data ⇒ same plan and
  same recommendation (critical for a reliable demo).

---

## 7. Tool calling

- The Agent calls tools by **name** with **structured args** and receives **structured results**
  (not prose) so it can reason/score over them.
- Tool interfaces (contracts in [`API_CONTRACTS.md` §6](API_CONTRACTS.md)):

| Tool | Purpose | Future owner |
|------|---------|--------------|
| `search_routes` | Find candidate multi-modal routes. | B |
| `get_fare_estimate` | Estimate fare(s) for a route/legs. | B (XGBoost) |
| `get_delay_prediction` | Predict delay risk/minutes. | B (LSTM) |
| `get_route_details` | Full leg-by-leg detail. | B |
| `check_availability` | Availability status (simulated). | C |
| `prepare_booking` | Prepare (never commit) a booking/hold. | C |

- **Observe then reason:** tool output feeds evaluation; the Agent must not skip analysis or
  pass results through blindly.
- **Idempotent reads** are safe to repeat; `prepare_booking` only **prepares**.
- **MVP:** all tools are **mocked** behind these signatures; B/C replace them later with **no
  signature change**.

---

## 8. Decision making & route scoring

**Conceptual model (refined in A6 — Route Decision Engine):**

1. **Filter** out any candidate that violates a **hard constraint** (§9). These are invalid.
2. **Score** survivors on **soft preferences** (§10) → a normalized `score` (0–1).
3. **Penalize** delay risk and discomfort (e.g., long walks with heavy luggage, many transfers).
4. **Rank**; pick the top as `recommendation`; keep others as `alternatives` with trade-offs.
5. **Explain**: produce a `rationale` referencing the user's own constraints/preferences.

Scoring signals (examples): `total_fare_lkr`, `total_duration_min`, `transfers`, `walking_km`,
`delay_risk`, mode comfort, luggage fit. Weights are a **later-phase decision (A6)** — record
them here when chosen. **TBD:** exact scoring formula/weights.

---

## 9. HARD CONSTRAINTS (must be satisfied — non-negotiable)

A route violating a hard constraint is **invalid** and must be excluded (or explicitly presented
as "does not meet your requirement, because…").

| Hard constraint | Source field | Rule |
|-----------------|--------------|------|
| **Origin** | `origin` | Route must start at the traveler's stated origin. |
| **Destination** | `destination` | Route must actually reach the requested destination. |
| **Budget** | `budget` (LKR) | `total_fare_lkr <= budget`. Over-budget routes are not valid picks. |
| **Arrival deadline** | `arrival_deadline` | Estimated arrival `<= arrival_deadline`, accounting for predicted delay risk. |

Handling examples:

- If **every** route exceeds the LKR 2,000 budget → do **not** pick the cheapest and call it a
  success. Report: *"No route fits under LKR 2,000 at this time; the closest is LKR 2,350 —
  would you like to raise the budget or change the departure time?"*
- If the **arrival deadline** can't be met given predicted delays → surface the risk and the
  trade-off honestly.

---

## 10. SOFT PREFERENCES (optimize — may be traded off)

Soft preferences are **scored and balanced**; the Agent optimizes them but may trade one against
another, and must **explain** significant trade-offs.

| Soft preference | Signal | Direction |
|-----------------|--------|-----------|
| **Less walking** | `walking_km`, `walking_preference` | Minimize (esp. with heavy luggage). |
| **Less waiting** | transfer wait time | Minimize. |
| **Faster** | `total_duration_min` | Minimize. |
| **Fewer transfers** | `transfers` | Minimize. |
| **Comfort** | `luggage`, mode comfort, crowding | Maximize. |

> **Luggage-aware rule (golden demo):** with `luggage = "heavy"` and
> `walking_preference = "minimize"`, walking segments and multiple transfers are penalized more
> heavily — favor minimal walking and easy transfers, **but only among routes that satisfy the
> hard budget/deadline constraints.** This must be the result of **reasoning over data**, never
> a hard-coded answer.

---

## 11. Alternatives

- Always provide **alternatives** alongside the recommendation, each with honest `trade_offs`
  ("Cheaper but 2 transfers", "Fastest but more walking").
- Alternatives must also **respect hard constraints** (or be clearly marked as violating one,
  e.g., "over budget").
- Keep the set small and meaningful (typically 2–3).

---

## 12. Replanning (ADAPT)

**Triggers** for `REPLANNING`:

- A predicted delay makes a connection infeasible or breaches `arrival_deadline`.
- A leg becomes unavailable (`check_availability` → unavailable).
- New information changes the constraint set (user edits budget/time).
- A disruption signal arrives from Coder Wake monitoring (Workstream C, future).

**On re-plan the Agent must:**

1. Explain **what changed** ("The 14:10 bus is delayed ~40 min; you'd miss the connection.").
2. Re-run **SEARCHING → EVALUATING** over remaining options.
3. Present the **new** recommendation + why it's now best.
4. Preserve honesty about provenance and confidence.

---

## 13. Error handling

- Any state can transition to **ERROR**. Mark the failing step `error`; keep prior successful
  steps visible.
- Distinguish **tool/agent errors** (shown in the activity rail) from **validation errors**
  (input) from **infrastructure errors** (backend/network).
- Provide a **retry** path where sensible (`retryable` in the error envelope — see
  [`API_CONTRACTS.md` §5](API_CONTRACTS.md)).
- Legitimate **"no good route"** outcomes are **not** system errors — prefer a `200` response
  with a clear explanation over an HTTP error (decide once in A6/A9 and document it).
- Never leave the user with a blank screen, an infinite spinner, or a fabricated success.

---

## 14. Safety

- **No irreversible actions without explicit user confirmation.** Real booking/payment is
  Workstream C; `prepare_booking` only prepares/holds. The Agent must not commit.
- **Never expose secrets** (API keys, tokens) in responses, user-visible logs, or agent traces.
- **Respect user control:** the user can correct constraints and re-run; the Agent re-plans.
- **Fail safe:** on uncertainty, prefer a conservative, clearly-explained option over a risky
  unexplained one.

---

## 15. Honesty & data provenance (critical for the MVP)

- The MVP uses **mock / simulated** transit, fare, delay, and availability data — by design, for
  a reliable demo (see [`PROJECT.md`](PROJECT.md) and [`DEMO.md`](DEMO.md)).
- Every result carries `data_source`. Explanations and UI must **not** imply live accuracy that
  isn't there.
- Estimates (fares/delays) are presented as **estimates with uncertainty**, not guarantees.
- The Agent may say: *"Fares are estimates based on simulated data."*

---

## 16. The Agent MUST NOT

- **Hallucinate fares.** Never invent a price; fares come from a tool (or a labeled estimate).
- **Hallucinate availability.** Never claim seats/bookings exist without a tool result.
- **Invent transit schedules.** No made-up departure/arrival times.
- **Claim an action happened when it did not.** If a tool wasn't called or failed, say so.
- **Present mock data as real-time verified data.** Label it.
- **Ignore explicit user constraints.** A stated budget/deadline/origin/destination is binding.
- **Fabricate precision.** Don't present an estimate as an exact guarantee.
- **Silently drop a hard constraint** to make a route "work" — report honestly instead.
- **Perform irreversible actions without confirmation** (see §14).

> If the Agent cannot satisfy the request, the correct behavior is to **say so clearly** and
> offer the nearest alternatives + what the user could relax — never invent a fake success.

---

## 17. Explanation requirements

Every completed plan includes a **ReasoningSummary** that:

- States the recommended route in **one human sentence**.
- References the user's **own** constraints ("under your LKR 2,000 budget", "minimal walking with
  a heavy bag").
- Names the key **trade-off(s)** vs alternatives.
- Notes any **assumptions** or **risks** (delay risk, estimated fares).
- Avoids jargon; no raw tool dumps in the summary (those live in the activity trace).

---

## 18. Guardrails quick reference

| Situation | Correct behavior |
|-----------|------------------|
| No route within budget | Report honestly; suggest relaxing budget/time; do **not** fake success. |
| Fare unknown | Call `get_fare_estimate`; if unavailable, say "estimate unavailable" — never invent. |
| Delay risk high | Surface it; consider re-planning; don't hide it. |
| Missing destination | Ask or state the assumption; don't guess silently. |
| Booking requested | `prepare_booking` only; explicit confirmation before any real commit (Workstream C). |
| Data is mock | Label `data_source`; never present as real-time. |
| Tool failed | Mark step `error`; explain; retry or degrade gracefully. |

---

## 19. Scope reminder

This document defines **behavior/contract**, not implementation. Building the actual agent
(Qwen integration, orchestration, tool-calling loop, scoring) happens in later phases
(**A2–A7**). During **A1 — Project Foundation**, do **not** implement agent logic — only keep
this spec consistent so all future work aligns.
