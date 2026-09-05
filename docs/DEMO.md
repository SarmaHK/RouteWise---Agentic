# DEMO.md — RouteWise Agentic

> Source of truth #8. The **hackathon demo** script and the **mock scenarios** that make it
> reliable. Read with [`AGENT_SPEC.md`](AGENT_SPEC.md) (states/behavior),
> [`WORKSTREAMS.md`](WORKSTREAMS.md) (who provides what), and
> [`PROJECT.md`](PROJECT.md) (golden scenario).
>
> **Status:** demo **plan** + partial implementation. This document defines what the demo must show
> so all three workstreams build toward one coherent story. **A3 demonstrates steps 1–10 of the
> §3 walkthrough over mock data** (request → understanding → planning → mock search → evaluation →
> decision → explanation → alternatives, with a MOCK tag), **A4 hardens the tool seam behind step 5**
> (a real registry + executor; the tool trace shows each tool's availability + data source), **A5
> makes step 5 autonomous + multi-step** (Qwen *selects* each tool call in a bounded loop; the trace
> can now show several model-chosen calls, each with its status/source and any `error_code`), **A6
> deepens steps 7–10** (each route card now carries a 1-based `rank`, a `valid` flag, grounded
> `strengths`, and structured `constraint_violations`, so an excluded route is *shown with its reason*
> rather than silently dropped), and **A7 makes steps 5–6 a real multi-tool intelligence run**
> (`search_routes` + `get_fare_estimate` + `get_delay_prediction` + `get_route_details` are all
> `AVAILABLE` on **one shared deterministic mock dataset**, so the trace shows a genuine
> search → enrich → evaluate workflow, the recommended route card gains a per-leg breakdown, and each
> timeline tool line is marked ✓/✗ from its real status), and **A8 makes steps 1–10 a polished,
> judge-facing UI** (a two-column shell with a persistent **Agent activity rail**, the registered
> `ui`/`agent`/`travel` components, honest "Working…" loading + skeleton states, per-leg `DelayBadge`
> / `FareDisplay` / `ModeIcon`, and clear clarification / no-route / error banners — presentation
> only; the backend, contract and states are unchanged), and **A9 makes every run identifiable and
> the failure paths provably safe** (each response carries a `request_id` matching the `X-Request-Id`
> header and the backend's structured `event=…` logs; each trace action carries a machine-readable
> `kind`; the golden run was re-validated end-to-end and all eleven documented failure scenarios —
> missing origin/destination, no valid routes, tool failure, unknown tool, invalid tool arguments,
> repeated tool call, iteration limit, malformed AI output, backend unavailable, stale state after a
> new request — fail or recover predictably). **Step
> 11 (disruption/re-planning) and step 12 (Travel Pass) are not built** (A10+ / Workstream C). All
> route data is **mock**.

---

## 1. Golden scenario

> **"I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000, but I have a heavy
> bag and don't want to walk."**

The demo must prove the Agent can **reason**, not recite:

- **Hard constraints:** origin = Colombo Fort, destination = Ella, budget ≤ **LKR 2,000**.
- **Soft preferences:** **heavy luggage** → comfort/fewer transfers; **minimize walking**.
- The final answer must be the **result of reasoning over data + tools** — **never hard-coded.**

---

## 2. What the demo must prove

1. Natural-language **understanding** + **constraint extraction**.
2. **Multi-modal** route discovery (train/bus/tuk/walk).
3. **Hard-constraint** enforcement (budget, origin/destination, any deadline).
4. **Soft-preference** optimization (minimal walking, luggage-aware comfort, fewer transfers).
5. **Transit intelligence** (fares, delay risk) via tools.
6. **Comparison** of alternatives with honest trade-offs.
7. **Autonomous action** (simulated) with a confirmation gate for anything irreversible.
8. **Explanation** of the decision in human terms.
9. **Adaptation**: a disruption triggers **re-planning** live.
10. **Delivery** of an offline-ready **Travel Pass** view.
11. **Honesty**: mock/simulated data is clearly labeled — never presented as real-time.

---

## 3. Demo walkthrough (12 steps → agent states)

| # | Demo step | What the presenter shows | Agent state | UI element |
|---|-----------|--------------------------|-------------|------------|
| 1 | **User request** | Type the golden scenario into the trip form. | IDLE → UNDERSTANDING | `TripForm` |
| 2 | **Agent understanding** | Activity rail lights up: "Understanding your request…" | UNDERSTANDING | `AgentActivity`, `AgentStatus` |
| 3 | **Constraint extraction** | Extracted constraints appear as chips: Colombo Fort → Ella, budget LKR 2,000, heavy bag, minimal walking. | UNDERSTANDING | constraint chips |
| 4 | **Planning** | "Planning your journey…" — agent outlines which tools it will call. | PLANNING | `AgentStep` |
| 5 | **Tool calls** | Expandable **mono** tool traces — **A5:** the sequence is **model-selected** (Qwen picks each call in a bounded loop). **A7:** there is now a real multi-step sequence to pick from — `search_routes(...)` then `get_fare_estimate(...)` / `get_delay_prediction(...)` / `get_route_details(...)` per returned route, all `AVAILABLE` on **mock** data (✓/✗ shown from each call's real status). `check_availability` / `prepare_booking` remain honest `NOT_IMPLEMENTED` stubs. | SEARCHING (→ EXECUTING for an action tool) | `AgentStep` (tool trace) |
| 6 | **Transit intelligence** | Candidate routes stream in with fares + delay risk (labeled **simulated**). **A7:** those fares/delays now come from the mock intelligence tools and are **consistent with the candidates** (one shared dataset); the recommended route card also lists its **legs** (mode, from→to, duration, fare, walk, delay risk). | SEARCHING | `RouteCard`s |
| 7 | **Route evaluation** | "Comparing 3 routes…" — scores/trade-offs shown; over-budget routes filtered out. **A6:** every candidate is validated, normalized and scored deterministically; an excluded route keeps its structured violation (e.g. `BUDGET`) instead of disappearing. | EVALUATING | `RouteCard`, `FareDisplay`, `DelayBadge` |
| 8 | **Decision** | Recommended route highlighted (primary accent + "Recommended"). **A6:** the winner is the top **valid** candidate by `rank`; with zero valid candidates no route is recommended at all. | EVALUATING → EXECUTING | `RouteCard` (recommended) |
| 9 | **Explanation** | `ReasoningSummary`: *"Meets your LKR 2,000 budget, minimizes walking with a heavy bag…"* **A6:** reasons and `strengths` quote the candidate's real values only — never a fact that does not exist. | COMPLETED | `ReasoningSummary` |
| 10 | **Alternatives** | 1–2 alternatives with honest trade-offs ("Cheaper but 2 transfers"). **A6:** valid runners-up first (by `rank`), then excluded candidates (marked `valid: false` + their violations), capped at 3; never fabricated. | COMPLETED | `RouteCard`s |
| 11 | **Disruption / re-planning** | Inject a delay (see §4.2) → "Connection at risk — re-planning…" → new recommendation + why it changed. | REPLANNING → SEARCHING → EVALUATING → COMPLETED | `AgentActivity`, updated `RouteCard` |
| 12 | **Final travel output** | Offline-ready **Travel Pass** view (times, legs, refs, QR placeholder). | COMPLETED | `TravelPass` |

> Steps 5–6 (transit intelligence) are **Workstream B** territory; steps 11–12 (execution /
> pass delivery) touch **Workstream C**. In the demo they are backed by **mocks/simulation**
> behind the real interfaces (see [`WORKSTREAMS.md`](WORKSTREAMS.md)).
>
> **A3–A7 coverage:** steps **1–10** run end-to-end over the deterministic **mock** intelligence
> provider — the agent *reasons* (filters hard constraints, scores soft preferences, ranks); it does
> not recite a hard-coded winner. Step **5** is a **bounded multi-step Qwen loop** (A5): the model
> *selects* each tool call, which runs through the A4 seam (registry → executor → structured result).
> With no API key the **mock** planner (`model: mock-qwen`) drives a realistic scenario —
> `search_routes` for the corridor, then `get_fare_estimate` for every returned route, then
> `get_delay_prediction` for every returned route, then `get_route_details` for every returned route,
> then finalize.
> All four data tools are `AVAILABLE` on **mock** data read from **one shared dataset**
> (`backend/app/tools/intelligence.py`), so they can never disagree about a route; an unknown id
> (e.g. `R999`) is a structured `ROUTE_NOT_FOUND` failure, not invented numbers.
> `check_availability` / `prepare_booking` are still honest `NOT_IMPLEMENTED` stubs (C), so if the model
> calls them the trace shows their status/source (and `error_code`) without fabricating numbers. The
> loop is capped at `MAX_AGENT_ITERATIONS` (default 8) and never invents a recommendation on the limit.
> Steps **6–10** are decided by the **A6**
> engine over those tool-gathered candidates: malformed/duplicate candidates are skipped, impossible
> values count as unknown (recorded in `assumptions`), features are min–max normalized, `walking_preference`
> and `luggage` re-weight the score, `delay_risk`/known delay minutes are penalized (**consumed, never
> predicted**), and the result is ranked with a deterministic tie-break. **A7 feeds that engine but does
> not change it** — observed tool results are merged per route id with the **candidate kept
> authoritative** and any contradiction reported. Steps **11–12** (re-planning,
> Travel Pass) are **not implemented** yet.
>
> **A8 (UI):** steps 1–10 are now presented by the real registered components in a two-column shell
> (`TripForm` → the `AgentStatus`/`AgentActivity`/`AgentStep` rail → `RouteCard`/`RouteTimeline`/
> `TransportLeg`/`FareDisplay`/`DelayBadge` → `ReasoningSummary` → `TravelRequestSummary`). The UI is
> presentation only — it renders the same single-shot `POST /api/route/plan` response; there is
> no live streaming **by decision** (A9 settled the delivery mechanism as single-shot: the rail fills
> from the returned `agent_actions[]`, and loading is an honest
> indeterminate "Working…"). Steps 11–12 remain unbuilt (A10+ / Workstream C).

---

## 4. Mock scenarios

The demo must be reproducible. Four scripted scenarios exercise the agent's logic. **All data is
mock/simulated and labeled as such** (`data_source`). Values below are **illustrative** — the
real numbers come from B's tools (mocked in the MVP); do **not** treat them as verified facts and
do **not** hard-code the "winner".

### 4.1 Normal route (happy path)

- **Trigger:** golden scenario, no disruptions.
- **Expected agent behavior:** discover candidates, filter any over LKR 2,000, prefer minimal
  walking + fewer transfers (heavy bag), recommend the best, explain, show alternatives.
- **Illustrative candidates (SIMULATED):**

  | Route | Modes | Est. total fare | Est. time | Walk | Transfers | Delay risk |
  |-------|-------|-----------------|-----------|------|-----------|------------|
  | R1 | walk→tuk + train (Colombo→Ella) | ~LKR 1,600 | ~7h | low | 1 | low |
  | R2 | bus (direct) + short walk | ~LKR 1,200 | ~6h | medium | 0 | moderate |
  | R3 | tuk + train + connecting bus | ~LKR 2,350 ❌ over budget | ~5.5h | low | 2 | low |

  **Reasoned outcome:** R3 is **excluded** (violates the hard budget). Between R1 and R2, the
  agent weighs minimal walking + heavy bag (favors R1's low walk / train comfort) vs cost/time
  (R2 cheaper/faster). The **agent decides and explains** — the demo shows the reasoning, not a
  pre-baked answer.

  **A6, measured (mock fixtures, deterministic):** with `heavy` + `minimize` the weights become
  `walking 0.502392 / transfers 0.178628 / duration 0.159490 / fare 0.159490`, and **R1 wins at
  0.472** over **R2 at 0.408**; R3 is excluded with a structured `BUDGET` violation (LKR 2,350 >
  LKR 2,000) and is still shown as a marked alternative. Remove the preferences and the *same*
  candidates select **R2 at 0.610** over R1 at 0.270 — and `heavy` alone (R2 0.544) or `minimize`
  alone (R2 0.481) also select R2. It is the **combination** that tips the decision, which is exactly
  the "reasoning, not recitation" proof point.

  **A7, measured end-to-end (mock planner, no API key, deterministic):** the same numbers now come out
  of the **full agent loop**, not just the engine in isolation. One `POST /api/route/plan` with the
  golden request produces a **14-action** trace over only the five canonical states
  (`UNDERSTANDING → PLANNING → SEARCHING ×10 → EVALUATING → COMPLETED`):
  `search_routes(Colombo Fort → Ella)` returns R1/R2/R3 → `get_fare_estimate` for **R1, R2, R3** →
  `get_delay_prediction` for **R1, R2, R3** → `get_route_details` for **R1, R2, R3** (all ten calls
  `status: done`, `data_source: mock`). Result:
  **recommendation R1 at 0.472**, **alternative R2 at 0.408**, **R3 excluded** (`BUDGET` — LKR 2,350 >
  LKR 2,000, still shown as a marked alternative), and **`legs` = R1-L1 (walk) / R1-L2 (tuk) /
  R1-L3 (train)** whose durations, fares and walking distances sum exactly to R1's candidate totals.
  Every tool result carries `data_source: mock`; the winner is computed from the observed evidence and
  is **not** hard-coded anywhere.

### 4.2 Delayed route (delay risk → re-plan)

- **Trigger:** inject a delay on the chosen route's key leg (e.g., train delayed ~40 min) via the
  mock `get_delay_prediction` / a Coder Wake-style disruption signal.
- **Expected:** `DelayBadge` escalates (moderate/high); if a connection or deadline is at risk →
  **REPLANNING** → agent re-searches, presents a new recommendation, and explains **what changed
  and why**.
- **Shows:** the **ADAPT** stage and honest delay handling (no fabricated on-time claims).
- **A7:** `get_delay_prediction` is now an `AVAILABLE` **mock** tool returning
  `{ delay_risk, delay_min_estimate, … , data_source: mock }` from the shared dataset (R1 `low`/10 min,
  R2 `moderate`, R3 `low`), and the A6 engine already penalizes both risk and known minutes — so the
  *consume-a-delay* half of this scenario is live. The **REPLANNING** half (a disruption signal that
  re-opens the loop) is **not** built: it needs the Workstream-C signal and lands in A8+.

### 4.3 Unavailable route (availability → fallback)

- **Trigger:** mock `check_availability` returns **unavailable/limited** for a leg (e.g., a
  booked-out train class).
- **Expected:** agent marks that option unavailable, falls back to the next-best **within
  budget**, and explains the substitution. If nothing fits, it **says so honestly** and suggests
  what to relax (budget/time) — never fakes success.
- **Shows:** hard-constraint integrity + honest failure handling.
- **A6:** `availability` is an explicit hard constraint — a candidate is excluded **only** when it is
  explicitly `unavailable`, and the exclusion carries a structured `AVAILABILITY` violation. The A-phase
  default is `unknown`, which is **not** treated as a violation (the agent never claims real seats).
- **A7:** **unchanged — deliberately.** `check_availability` is a Workstream-C tool and stays an honest
  `NOT_IMPLEMENTED` stub, so this scenario still cannot be demoed live; if the model calls it, the trace
  shows `not_implemented` + `NOT_IMPLEMENTED` rather than a fabricated seat count.

### 4.4 Re-planning (constraint change)

- **Trigger:** user edits a constraint mid-flow (e.g., lowers budget to LKR 1,300, or adds an
  arrival deadline) **or** a combined delay+availability disruption.
- **Expected:** agent re-runs **SEARCHING → EVALUATING**, updates the recommendation, and
  explains the new trade-offs against the changed constraints.
- **Shows:** the agent reacts to new information rather than sticking to a stale plan.

---

## 5. Mock-data policy (identify mock data clearly)

- Every fare, delay, availability, and schedule in the demo is **mock/simulated**. Each result
  carries `data_source` = `mock` or `simulated` (see
  [`API_CONTRACTS.md`](API_CONTRACTS.md)).
- The UI shows a subtle **"simulated"** tag on mock data and on simulated actions
  (see [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)).
- **Never** present mock data as real-time/verified. The Agent must not claim an action happened
  when it was only simulated (see [`AGENT_SPEC.md` §15–16](AGENT_SPEC.md)).
- Mock values should be **realistic** (plausible Sri Lankan routes, LKR fares, believable
  delays/times) so the demo is credible — but they are **fixtures**, not live feeds.
- **A7 — one shared fixture, not four.** All mock intelligence lives in a single module
  (`backend/app/tools/intelligence.py`, 7 routes over 3 corridors) that every data tool reads, and it
  contains **no randomness**: the same request always produces the same trace and the same decision.
  Its figures are internally consistent by construction (leg durations/fares/walking sum to the route
  totals; vehicle legs − 1 = transfers), so the demo can be challenged on any number and every view
  will agree.
- Mock fixtures live behind the **same tool interfaces** B/C will implement, so swapping in real
  data changes nothing in the demo flow (only the source). **That swap point is now concrete:**
  replace `intelligence.py`'s accessors with real GTFS/PostGIS/XGBoost/LSTM data, flip `data_source`,
  and the agent, decision engine, API and UI are untouched.

---

## 6. Demo resilience (fallbacks)

- **Backend down?** The frontend `services/mock` can supply a clearly-labeled simulated response
  so the flow still runs end-to-end (see [`ARCHITECTURE.md` §3.3](ARCHITECTURE.md)).
- **Deterministic mode:** a fixed mock seed so the golden scenario produces a stable, repeatable
  result for the live demo (agent still *reasons*; inputs are fixed).
- **Pre-warm** tool responses to avoid live latency during the pitch.
- **Rehearse the re-plan trigger** (steps 11) so it fires reliably on stage.

---

## 7. Presenter talk track (skeleton)

1. **Problem:** tourists juggle budget, luggage, walking, delays across many transport modes —
   no app plans it coherently.
2. **Our approach:** an **agentic** coordinator that UNDERSTANDS → REASONS → ACTS → ADAPTS →
   DELIVERS.
3. **Live:** type the golden scenario → watch the agent think (activity rail) → see constraints
   extracted → routes compared → decision explained.
4. **Adapt:** inject a delay → agent re-plans live.
5. **Deliver:** show the offline Travel Pass.
6. **Honesty:** point out the "simulated" tags — the reasoning is real; the feeds are mocked for
   reliability, and swap to live B/C services behind the same interfaces.

---

## 8. Demo success criteria (checklist)

- [ ] Golden scenario runs end-to-end without hard-coding the answer.
- [ ] Constraints (budget, luggage, walking, origin/destination) visibly extracted and respected.
- [ ] Over-budget route excluded; alternatives shown with trade-offs.
- [ ] Decision explained in human language referencing the user's constraints.
- [ ] A disruption triggers **REPLANNING** and an updated, explained recommendation.
- [ ] Travel Pass view renders (offline-ready contract).
- [ ] All 9 agent states appear correctly across the scenarios.
- [ ] Mock/simulated data is clearly labeled; nothing presented as real-time.
- [ ] Demo is repeatable (deterministic seed) and resilient (fallbacks ready).

> **This is the target all workstreams build toward.** A3 delivers steps 1–10 over mock data, A4
> hardens the tool execution behind step 5, A5 makes that step an autonomous multi-step Qwen loop,
> A6 deepens the evaluation/decision behind steps 7–10, and A7 gives steps 5–6 a complete,
> consistent multi-tool mock intelligence run (search + fare + delay + details, legs on the card),
> and A8 presents steps 1–10 through the polished two-column agent-experience UI, and A9 freezes the
> pipeline as the observable, regression-protected integration baseline;
> the full demo (including steps 11–12) completes across A10 + Workstreams B/C.
