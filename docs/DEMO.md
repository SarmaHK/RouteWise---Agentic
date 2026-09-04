# DEMO.md — RouteWise Agentic

> Source of truth #8. The **hackathon demo** script and the **mock scenarios** that make it
> reliable. Read with [`AGENT_SPEC.md`](AGENT_SPEC.md) (states/behavior),
> [`WORKSTREAMS.md`](WORKSTREAMS.md) (who provides what), and
> [`PROJECT.md`](PROJECT.md) (golden scenario).
>
> **Status:** demo **plan** + partial implementation. This document defines what the demo must show
> so all three workstreams build toward one coherent story. **A3 now demonstrates steps 1–10 of the
> §3 walkthrough over mock data** (request → understanding → planning → mock search → evaluation →
> decision → explanation → alternatives, with a MOCK tag); **step 11 (disruption/re-planning) and
> step 12 (Travel Pass) are not built** (A4+ / Workstream C). All route data is **mock**.

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
| 5 | **Tool calls** | Expandable **mono** tool traces: `search_routes(...)`, `get_fare_estimate(...)`, `get_delay_prediction(...)`. | SEARCHING | `AgentStep` (tool trace) |
| 6 | **Transit intelligence** | Candidate routes stream in with fares + delay risk (labeled **simulated**). | SEARCHING | `RouteCard`s |
| 7 | **Route evaluation** | "Comparing 3 routes…" — scores/trade-offs shown; over-budget routes filtered out. | EVALUATING | `RouteCard`, `FareDisplay`, `DelayBadge` |
| 8 | **Decision** | Recommended route highlighted (primary accent + "Recommended"). | EVALUATING → EXECUTING | `RouteCard` (recommended) |
| 9 | **Explanation** | `ReasoningSummary`: *"Meets your LKR 2,000 budget, minimizes walking with a heavy bag…"* | COMPLETED | `ReasoningSummary` |
| 10 | **Alternatives** | 1–2 alternatives with honest trade-offs ("Cheaper but 2 transfers"). | COMPLETED | `RouteCard`s |
| 11 | **Disruption / re-planning** | Inject a delay (see §4.2) → "Connection at risk — re-planning…" → new recommendation + why it changed. | REPLANNING → SEARCHING → EVALUATING → COMPLETED | `AgentActivity`, updated `RouteCard` |
| 12 | **Final travel output** | Offline-ready **Travel Pass** view (times, legs, refs, QR placeholder). | COMPLETED | `TravelPass` |

> Steps 5–6 (transit intelligence) are **Workstream B** territory; steps 11–12 (execution /
> pass delivery) touch **Workstream C**. In the demo they are backed by **mocks/simulation**
> behind the real interfaces (see [`WORKSTREAMS.md`](WORKSTREAMS.md)).
>
> **A3 coverage:** steps **1–10** run end-to-end over the deterministic **mock** candidate provider
> — the agent *reasons* (filters hard constraints, scores soft preferences, ranks); it does not
> recite a hard-coded winner. Step **5** calls `search_routes` only (fares + delay-risk ride on the
> mock candidates; separate fare/delay tools are honest `not_implemented` stubs, A4+). Steps
> **11–12** (re-planning, Travel Pass) are **not implemented** yet.

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

### 4.2 Delayed route (delay risk → re-plan)

- **Trigger:** inject a delay on the chosen route's key leg (e.g., train delayed ~40 min) via the
  mock `get_delay_prediction` / a Coder Wake-style disruption signal.
- **Expected:** `DelayBadge` escalates (moderate/high); if a connection or deadline is at risk →
  **REPLANNING** → agent re-searches, presents a new recommendation, and explains **what changed
  and why**.
- **Shows:** the **ADAPT** stage and honest delay handling (no fabricated on-time claims).

### 4.3 Unavailable route (availability → fallback)

- **Trigger:** mock `check_availability` returns **unavailable/limited** for a leg (e.g., a
  booked-out train class).
- **Expected:** agent marks that option unavailable, falls back to the next-best **within
  budget**, and explains the substitution. If nothing fits, it **says so honestly** and suggests
  what to relax (budget/time) — never fakes success.
- **Shows:** hard-constraint integrity + honest failure handling.

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
- Mock fixtures live behind the **same tool interfaces** B/C will implement, so swapping in real
  data changes nothing in the demo flow (only the source).

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

> **This is the target all workstreams build toward.** A3 delivers steps 1–10 over mock data; the
> full demo (including steps 11–12) completes across A4–A9 + Workstreams B/C.
