# API_CONTRACTS.md — RouteWise Agentic

> Source of truth #4. Defines the **API contract philosophy**, the reserved primary endpoint,
> and the **future tool interfaces**. These are **contracts** — at this stage they are
> interfaces/mock shapes, **not** implementations.
>
> **Do not implement real Workstream B/C functionality.** Do not silently change a contract
> once consumers exist — propose the change first (see
> [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) rule 11).

---

## 0. Current vs. future status

Everything in this document is a **contract**, not an implementation. Two status labels are
used throughout, so no reader mistakes a plan for a built feature:

- **CURRENT (agreed now).** The shape/signature is fixed and **mockable today**. Workstream A
  builds against it with mocks; frontend types mirror it. Nothing here is "live".
- **FUTURE (implemented later).** A real implementation is owned by another workstream/phase
  and swapped in **behind the same signature**. Do not build it during A1.

| Contract element | Status | Owner / phase |
|------------------|--------|---------------|
| `POST /api/route/plan` shape (§2) | CURRENT (implemented) | A — **A3 agent decision** (mock candidates + deterministic scoring); real transit data A9 |
| `TravelRequest` normalized-request shape (§2.1) | CURRENT (implemented) | A — A2 |
| `GET /health` liveness probe (§2) | CURRENT (implemented) | A — A1 |
| Route / leg / recommendation shapes (§3) | CURRENT (mock) | A → B (real data) |
| `agent_actions[]` shape (§4) | CURRENT | A |
| Error envelope (§5) | CURRENT | A |
| `search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details` (§6) | CURRENT signature / FUTURE impl | B |
| `check_availability`, `prepare_booking` (§6) | CURRENT signature / FUTURE impl | C |
| Delivery mechanism: single response vs SSE/WebSocket (§4) | FUTURE (undecided) | A — decided A5/A8/A9 |
| `GET /api/agent/status`, `GET /api/agent/stream` (§7) | FUTURE (reserved) | A — decided A5/A8/A9 |
| Live GTFS/GTFS-RT, PostGIS, real ML, real booking, cloud deploy | FUTURE | B / C |

> **Rule:** a FUTURE item must never be presented as CURRENT in code, UI, or the demo. Mocks
> carry `data_source: mock | simulated` (see [`AGENT_SPEC.md` §15](AGENT_SPEC.md)).

---

## 1. Contract philosophy

1. **Contracts first.** Frontend and backend agree on shapes here before code is written.
   Types on both sides mirror this document.
2. **Stable boundaries.** Workstream A exposes a stable API to the frontend and consumes
   stable **tool interfaces** that Workstream B/C will later implement. Mocks honor the same
   shapes so swapping real services in is non-breaking.
3. **JSON everywhere.** `Content-Type: application/json`. `snake_case` field names (matches
   Python/FastAPI and the proposal's examples).
4. **Explicit status.** Every planning response carries an **agent state** from the canonical
   list in [`AGENT_SPEC.md` §5](AGENT_SPEC.md) — never a free-form string.
5. **Honest data.** Mock/simulated results are labeled as such; the API never presents mock
   data as real-time (see [`AGENT_SPEC.md` §15](AGENT_SPEC.md)).
6. **Versioning.** All endpoints live under `/api`. If a breaking change is unavoidable,
   introduce `/api/v2/...` rather than mutating `/api/...` in place.
7. **Errors are structured.** Consistent error envelope (§5), meaningful HTTP codes.

---

## 2. Reserved primary endpoint

### `POST /api/route/plan`

Submit a travel request; receive the agent's plan/recommendation.

- **Owner:** Workstream A.
- **Status:** the **real** transit-data planning lands in **A9 — Final API & Agent State**.
  **A1 shipped an honest foundation stub** (`status: IDLE`); **A2 implemented Travel Request
  Understanding** (extraction into a `TravelRequest`, §2.1). **A3 now implements the agent
  orchestration & decision layer** at this path: after extraction it drives the canonical state
  machine (`UNDERSTANDING → PLANNING → SEARCHING → EVALUATING → COMPLETED`), calls a **mock**
  `search_routes` tool, and a **deterministic decision engine** returns a `recommendation`,
  `alternatives`, the full `agent_actions[]` trace, and a concise `reasoning` — all
  `data_source: mock`. If a hard constraint is missing the agent **stops before deciding** and
  returns `status: UNDERSTANDING` with the clarification (A2 behaviour preserved). Real transit
  search / ML scoring remains FUTURE (Workstream B, surfaced in A9).

#### Request (conceptual)

```json
{
  "raw_text": "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000...",
  "origin": "...",
  "destination": "...",
  "budget": 2000,
  "currency": "LKR",
  "luggage": "...",
  "walking_preference": "...",
  "departure_time": "...",
  "arrival_deadline": "...",
  "preferences": {}
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `raw_text` | string | optional* | **Added in A2** (resolves the decision reserved below). The natural-language request; the primary A2 extraction input. |
| `origin` | string | optional* | Free text or normalized place name (e.g., "Colombo Fort"). In A2 it may be **extracted from `raw_text`** instead of sent explicitly. |
| `destination` | string | optional* | e.g., "Ella". May be extracted from `raw_text` in A2. |
| `budget` | number | optional | Max total fare in **LKR**. Treated as a **hard constraint** when present. |
| `currency` | string | optional | **Added in A2.** Currency for `budget`; defaults to **LKR**. |
| `luggage` | string/enum | optional | `"none" \| "light" \| "heavy"`. Affects comfort/transfers. |
| `walking_preference` | string/enum | optional | `"minimize" \| "normal" \| "ok"`. **Soft preference.** |
| `departure_time` | string (ISO 8601) | optional | When the traveler wants to leave. |
| `arrival_deadline` | string (ISO 8601) | optional | Must-arrive-by. **Hard constraint** when present. |
| `preferences` | object | optional | Open bag for extra soft preferences (fewer transfers, comfort, scenic, etc.). |

> \* **At least one of `raw_text`, `origin`, or `destination` is required** (A2). An empty body is
> rejected with `422` (§5). Previously `origin`+`destination` were both mandatory; A2 **relaxes**
> them to optional because they can be extracted from `raw_text` — an additive/relaxing change
> noted per §9.
>
> **Resolved (A2):** the natural-language request is sent as the optional `raw_text` field (added
> above, exactly as this doc reserved). The structured fields remain the **normalized output**
> shape, now returned as `TravelRequest` (§2.1).

#### Response (conceptual)

```json
{
  "status": "...",
  "request": {},
  "recommendation": {},
  "legs": [],
  "alternatives": [],
  "agent_actions": [],
  "reasoning": "..."
}
```

| Field | Type | Notes |
|-------|------|-------|
| `status` | enum | One of the canonical **Agent states** ([`AGENT_SPEC.md` §5](AGENT_SPEC.md)): `IDLE, UNDERSTANDING, PLANNING, SEARCHING, EVALUATING, EXECUTING, REPLANNING, COMPLETED, ERROR`. **A3 returns `COMPLETED`** with a mock decision, or **`UNDERSTANDING`** when clarification is required (the agent stops before deciding); live-data planning matures in A9. |
| `request` | object | The **normalized/extracted** `TravelRequest` (§2.1) the agent understood: origin, destination, hard constraints, soft preferences, and any **missing info**/clarification it detected. Lets the UI echo constraints back. |
| `recommendation` | object | The chosen route + rationale. See §3. |
| `legs` | array | Ordered legs of the recommended route. See §3. |
| `alternatives` | array | Other candidate routes with trade-offs (same shape as recommendation). |
| `agent_actions` | array | Ordered log of what the agent did: states entered, tools called, results summary, decisions. Drives the Agent activity UI. See §4. |
| `reasoning` | string? | **Added in A3** (additive, §9). A concise, observable explanation of the decision or clarification (feeds `ReasoningSummary`, [`DESIGN_SYSTEM.md` §12.9](DESIGN_SYSTEM.md)). Never hidden chain-of-thought. |

#### 2.1 `TravelRequest` — the normalized request (A2)

`response.request` is a **`TravelRequest`**: the validated, normalized understanding of the trip.
Every travel-specific field is **optional** — the extractor **never invents** values (honesty,
[`AGENT_SPEC.md` §15](AGENT_SPEC.md)). Missing hard constraints are surfaced, not fabricated.

```json
{
  "origin": "Colombo Fort",
  "destination": "Ella",
  "budget": 2000,
  "currency": "LKR",
  "luggage": "heavy",
  "walking_preference": "minimize",
  "departure_time": null,
  "arrival_deadline": null,
  "preferences": {},
  "raw_text": "I am at Colombo Fort and need to reach Ella under a budget of LKR 2,000...",
  "clarification_required": false,
  "missing_fields": [],
  "clarification_questions": [],
  "assumptions": [],
  "extraction_source": "mock"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `origin` / `destination` | string? | Extracted place names; `null` when not stated. |
| `budget` / `currency` | number? / string | Max fare + currency (default **LKR**); `budget` is `null` when unstated. |
| `luggage` | enum? | `none \| light \| heavy`; `null` when unstated. |
| `walking_preference` | enum? | `minimize \| normal \| ok`; `null` when unstated. |
| `departure_time` / `arrival_deadline` | string (ISO 8601)? | `null` when unstated. |
| `preferences` | object | Other preserved soft preferences (e.g., `{ "cost": "cheap" }` from "cheaply"). |
| `raw_text` | string? | The original request, echoed for transparency. |
| `clarification_required` | boolean | `true` when a hard constraint (`origin`/`destination`) is missing. |
| `missing_fields` | string[] | Names of required fields that are absent. |
| `clarification_questions` | string[] | Short human-readable questions for the missing fields. |
| `assumptions` | string[] | Any safe assumption recorded (e.g., "assumed today's date for a stated time"). |
| `extraction_source` | enum? | **Honesty flag:** `mock` (deterministic offline extractor) `\|` `qwen` (real Model Studio). |

### `GET /health` — liveness probe (implemented in A1)

An infrastructure probe (not part of the versioned `/api` surface), mounted at the **root**:

```json
{ "status": "ok", "service": "routewise-agentic-backend", "phase": "A2-understanding" }
```

- **Owner:** Workstream A. **Status:** implemented in A1.
- The **contracted** field is `status` (`"ok"` when healthy); `service` and `phase` are additive
  metadata (§9). Consumed by the frontend foundation shell and by cloud load balancers
  ([`ARCHITECTURE.md` §11](ARCHITECTURE.md)). Never exposes secrets.

---

## 3. Route / leg / recommendation shapes (conceptual)

These are the **agreed shapes** to keep frontend and backend consistent. Field names may be
refined in later phases — **update this doc when that happens**.

### `recommendation` / an entry in `alternatives`

```json
{
  "id": "route_001",
  "summary": "Train Kandy→Ella + short tuk from Fort to Kandy",
  "total_duration_min": 420,
  "total_fare_lkr": 1850,
  "transfers": 2,
  "walking_km": 0.3,
  "within_budget": true,
  "delay_risk": "low",
  "score": 0.87,
  "rationale": "Meets your LKR 2,000 budget, minimizes walking with a heavy bag, and avoids a risky connection.",
  "reasons": ["Within your LKR 2,000 budget.", "Suitable for heavy luggage.", "Least walking of the viable routes."],
  "trade_offs": ["Slightly longer than the fastest option"],
  "is_recommended": true,
  "data_source": "mock"
}
```

### a `legs[]` entry

```json
{
  "id": "leg_1",
  "mode": "train",
  "from": "Colombo Fort",
  "to": "Ella",
  "departure_time": "2026-09-04T08:30:00+05:30",
  "arrival_time": "2026-09-04T15:10:00+05:30",
  "duration_min": 400,
  "fare_lkr": 1500,
  "walking_km": 0.0,
  "delay_risk": "low",
  "delay_min_estimate": 5,
  "notes": "Scenic hill-country line",
  "data_source": "mock"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `mode` | enum | Transport mode: `walk, tuk, bus, train, taxi, ferry`. Drives `TransportLeg` icon. |
| `fare_lkr` / `total_fare_lkr` | number | Money is **always LKR**, numeric. Rendered in **mono**. |
| `*_min` / `*_km` | number | Durations in **minutes**, distances in **km** — explicit units in names. |
| `delay_risk` | enum | `none, low, moderate, high`. Maps to `DelayBadge` tones. |
| `within_budget` | boolean | Hard-constraint check result; drives success/error styling. |
| `score` | number | 0–1 normalized ranking from the decision engine (**A3** deterministic scoring; refined with real data in A6). |
| `rationale` / `reasons` / `trade_offs` | string / array | Human explanation (feeds `ReasoningSummary`). `rationale` = headline reason; **`reasons`** (added in A3) = the concise list of observable decision factors; `trade_offs` = why an alternative ranked below the recommendation. |
| `data_source` | enum | `mock` \| `simulated` \| `live`. **Honesty flag** — MVP is `mock`/`simulated`. |

---

## 4. `agent_actions[]` shape (conceptual)

An ordered log the frontend renders via `AgentActivity`/`AgentStep`.

```json
{
  "seq": 3,
  "state": "SEARCHING",
  "label": "Searching routes & checking conditions",
  "detail": "Querying candidate routes Colombo Fort → Ella",
  "tool_call": {
    "name": "search_routes",
    "args": { "origin": "Colombo Fort", "destination": "Ella" },
    "status": "done",
    "result_summary": "3 candidate routes"
  },
  "timestamp": "2026-09-04T08:00:03Z",
  "status": "done"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `seq` | number | Order in the timeline. |
| `state` | enum | Canonical Agent state. |
| `label` / `detail` | string | Human-facing text. |
| `tool_call` | object? | Present when this step called a tool (§6). `status`: `pending\|running\|done\|error`. |
| `status` | enum | Step status: `pending \| active \| done \| error`. |
| `timestamp` | string (ISO 8601) | When it happened. |

> **Delivery mechanism** (single response vs. streaming/SSE/WebSocket) is a **later-phase
> decision**. The frontend hides it behind `useAgentStream()` (see
> [`ARCHITECTURE.md`](ARCHITECTURE.md)); the action **shape stays the same**
> either way.

---

## 5. Error envelope

All errors return a consistent body plus an appropriate HTTP status.

```json
{
  "status": "ERROR",
  "error": {
    "code": "budget_unreachable",
    "message": "No route found under LKR 2,000 at this departure time.",
    "details": {},
    "retryable": true
  }
}
```

| HTTP | Meaning |
|------|---------|
| `400` | Malformed request / failed validation. |
| `422` | Semantically invalid (e.g., origin == destination, impossible deadline). |
| `404` | Unknown resource (e.g., place not found in mock gazetteer). |
| `500` | Unexpected server error. |
| `502` | Upstream extraction produced invalid output (A2) — mapped to `code: bad_gateway`. Malformed model output is rejected, never silently accepted. |
| `503` | Downstream/tool unavailable (mock or real). |

- `error.code` is a **stable machine string** (clients may branch on it); `message` is
  human-readable and safe to show. `details` holds non-sensitive technical context.
- Domain "no result" cases (e.g., nothing within budget) may be returned as `200` with
  `status: "ERROR"` or `COMPLETED` + empty `recommendation` + explanatory `agent_actions` —
  **decide once in A6/A9 and document it here.** Prefer a `200` with a clear explanation over
  an HTTP error for legitimate "no good route" outcomes.

---

## 6. Future tool interfaces (contracts / mocks only)

These are the tools the agent may call. **At this stage they are interfaces/mock contracts.**
Workstream A defines and mocks them; Workstream B/C implement the real versions later behind
the **same signatures**. Do **not** implement real B/C functionality now.

| Tool | Signature (conceptual) | Returns (conceptual) | Future owner |
|------|------------------------|----------------------|--------------|
| `search_routes` | `search_routes(origin, destination, departure_time?, preferences?)` | List of candidate routes (id, modes, legs, rough fare/duration). | B |
| `get_fare_estimate` | `get_fare_estimate(route_id \| legs, currency="LKR")` | Estimated fare(s) + confidence; `data_source`. | B (XGBoost) |
| `get_delay_prediction` | `get_delay_prediction(route_id \| leg_id, at_time?)` | Delay risk level + estimated minutes; `data_source`. | B (LSTM) |
| `get_route_details` | `get_route_details(route_id)` | Full leg-by-leg detail, times, transfer points, walking segments. | B |
| `check_availability` | `check_availability(route_id \| leg_id, departure_time?)` | Availability status (available/limited/unavailable) — **simulated**. | C |
| `prepare_booking` | `prepare_booking(route_id, traveler_info)` | A **prepared, unconfirmed** booking/hold + refs; **never auto-confirms** without explicit user confirmation. | C |

**Tool contract rules:**

- Every tool result includes `data_source` (`mock`/`simulated`/`live`) so the agent and UI can
  stay honest.
- Tools are **idempotent where possible**; `prepare_booking` is **not** committing — actual
  irreversible booking is a Workstream C concern gated by explicit confirmation
  (see [`AGENT_SPEC.md` §14](AGENT_SPEC.md)).
- Tools return **structured** data (not prose) so the agent can reason/score over it.
- Mocks live behind these interfaces; swapping in real implementations must not change the
  signature or the agent code that calls them.

> Tool **implementations** (even mocks) are built in later phases (**A4 — Agent Tool System**,
> **A5 — Tool-Calling Orchestrator**, **A7 — Mock Intelligence Integration**). This document
> only fixes the **contract** so all workstreams agree.

---

## 7. Agent status / streaming endpoint (reserved)

If live agent activity is streamed rather than embedded, reserve:

- `GET /api/agent/status` → current canonical Agent state + last few `agent_actions`.
- `GET /api/agent/stream` (SSE) → incremental `agent_actions` as they occur.

**Status:** reserved; **not** decided/built in A1. Choose the mechanism in A5/A8/A9 and
record the final decision here.

---

## 8. Naming & type conventions

- **Field names:** `snake_case`. **Enums:** `UPPER_SNAKE_CASE` for agent states;
  `lower_snake`/short strings for modes and risk levels (documented per field).
- **Money:** numeric, currency explicit in the name (`*_lkr`) — default **LKR**.
- **Time:** ISO 8601 strings with timezone (`+05:30` for Sri Lanka) for timestamps;
  durations as numbers with unit suffix (`*_min`).
- **Distance:** numbers in km (`*_km`).
- **IDs:** stable strings (`route_001`, `leg_3`).
- **Booleans** for hard-constraint checks (`within_budget`, `is_recommended`).

---

## 9. Change policy

This document is the contract. Once the frontend or backend consumes a shape:

- **Additive** changes (new optional fields) are allowed — note them here.
  - **A3 (agent decision):** added `PlanResponse.reasoning` (optional string) and
    `Recommendation.reasons` (optional string[]). Both are additive — the A2 request contract and
    every pre-existing response field are unchanged, so no consumer breaks.
- **Breaking** changes require a proposal + version bump (§1.6) and updates to consumers.
- Never change a contract silently in code without updating this file in the same change.

---

## 10. Workstream communication map

How the three workstreams and the runtime layers exchange data. **All** cross-boundary
communication flows through the contracts in this document — never through shared internal
state or ad-hoc calls.

```
Frontend (React) — Workstream A UI
   |  POST /api/route/plan  (JSON, §2)            <- CURRENT contract, mocked
   v
Backend / FastAPI — Workstream A
   |  orchestrates the agent loop
   v
AI Agent (Qwen) — Workstream A
   |  calls tools (§6) via stable signatures       <- CURRENT signatures
   |---------------> Transit / ML tools (B): search_routes, get_fare_estimate,
   |                 get_delay_prediction, get_route_details   <- FUTURE real impl
   |---------------> Execution / Cloud tools (C): check_availability, prepare_booking
                     <- FUTURE real impl (never auto-commits)
```

| From → To | Channel / contract | Status |
|-----------|--------------------|--------|
| Frontend → Backend | `POST /api/route/plan` (§2) | CURRENT (mock) |
| Backend → Frontend | plan response: `recommendation` / `legs` / `alternatives` / `agent_actions` / `reasoning` (§2–4) | CURRENT (mock — A3 decision) |
| Backend → Frontend (live) | `GET /api/agent/status` · `GET /api/agent/stream` (§7) | FUTURE (reserved) |
| Agent → B tools | `search_routes`, `get_fare_estimate`, `get_delay_prediction`, `get_route_details` (§6) | CURRENT signature / FUTURE impl |
| Agent → C tools | `check_availability`, `prepare_booking` (§6) | CURRENT signature / FUTURE impl |
| B → Agent | structured route / fare / delay data + `data_source` | FUTURE |
| C → Agent | availability status / prepared (unconfirmed) booking + `data_source` | FUTURE |
| C → Agent (disruption) | disruption signal that triggers REPLANNING ([`AGENT_SPEC.md` §12](AGENT_SPEC.md)) | FUTURE |

> **Boundary rule:** A **decides**, B **informs**, C **acts**. Mocks honor the same shapes so
> swapping real B/C services in is non-breaking. Full ownership + pairwise exchanges:
> [`WORKSTREAMS.md`](WORKSTREAMS.md); system-level flow: [`ARCHITECTURE.md`](ARCHITECTURE.md).
