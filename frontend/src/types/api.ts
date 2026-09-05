/**
 * Shared domain types mirroring docs/API_CONTRACTS.md (A1 foundation + A2 TravelRequest +
 * A3 decision).
 *
 * Contract-first: these mirror the backend `schemas/` and API_CONTRACTS.md. A3 adds the
 * decision shapes (`Recommendation`, `Leg`, `ToolCall`) the agent now returns; the FULL domain
 * types are further expanded in A8. Keep in sync — do not diverge (types/README.md).
 */

/** The 9 canonical agent states (API_CONTRACTS §2; AGENT_SPEC §5). */
export type AgentState =
  | 'IDLE'
  | 'UNDERSTANDING'
  | 'PLANNING'
  | 'SEARCHING'
  | 'EVALUATING'
  | 'EXECUTING'
  | 'REPLANNING'
  | 'COMPLETED'
  | 'ERROR';

/** Honesty flag carried by results (API_CONTRACTS §3). */
export type DataSource = 'mock' | 'simulated' | 'live';

/** GET /health response (A1 foundation). */
export interface HealthResponse {
  status: string;
  service?: string;
  phase?: string;
}

/** Luggage condition (API_CONTRACTS §2). */
export type Luggage = 'none' | 'light' | 'heavy';

/** Walking preference — soft (API_CONTRACTS §2). */
export type WalkingPreference = 'minimize' | 'normal' | 'ok';

/** Provenance of an A2 extraction (mock = offline, qwen = real Model Studio). */
export type ExtractionSource = 'mock' | 'qwen';

/**
 * POST /api/route/plan request (API_CONTRACTS §2).
 *
 * A2 accepts EITHER structured fields OR free-form `raw_text`; `origin`/`destination` are
 * optional because they are extracted from `raw_text` (at least one input is required).
 */
export interface PlanRequest {
  origin?: string | null;
  destination?: string | null;
  budget?: number | null;
  currency?: string | null;
  luggage?: string | null;
  walking_preference?: string | null;
  departure_time?: string | null;
  arrival_deadline?: string | null;
  preferences?: Record<string, unknown>;
  raw_text?: string | null;
}

/**
 * The normalized request the agent understood (A2 output; mirrors backend TravelRequest).
 * Every travel-specific field is optional — the extractor never invents values. Missing hard
 * constraints are surfaced via the clarification fields (A2 brief §3/§6).
 */
export interface TravelRequest {
  origin?: string | null;
  destination?: string | null;
  budget?: number | null;
  currency?: string;
  luggage?: Luggage | null;
  walking_preference?: WalkingPreference | null;
  departure_time?: string | null;
  arrival_deadline?: string | null;
  preferences?: Record<string, unknown>;
  raw_text?: string | null;
  clarification_required: boolean;
  missing_fields: string[];
  clarification_questions: string[];
  assumptions: string[];
  extraction_source?: ExtractionSource | null;
}

/**
 * A tool invocation recorded on an agent action (API_CONTRACTS §4).
 *
 * A4 adds two additive, optional fields so the timeline can show tool-execution status safely
 * (A4 brief §15/§17): `availability` (the resolved tool's capability state) and `data_source`
 * (this call's provenance). A5 adds one more additive, optional field, `error_code` — the
 * structured failure code when a call did not succeed (A5 brief §10) — so the multi-step trace can
 * show *why* a tool call failed. All may be absent on older responses — the UI renders them only
 * when present, so the A3/A4 contract is preserved.
 */
export interface ToolCall {
  name: string;
  args?: Record<string, unknown>;
  status?: string; // pending | running | done | error
  result_summary?: string | null;
  /** Resolved tool capability state (A4): available | not_implemented | disabled | error. */
  availability?: string | null;
  /** Provenance of this tool call's output (A4). */
  data_source?: DataSource | null;
  /** Structured failure code when the call did not succeed (A5): e.g. NOT_IMPLEMENTED. */
  error_code?: string | null;
}

/** One entry of the agent-activity log (API_CONTRACTS §4). */
export interface AgentAction {
  seq: number;
  state: AgentState;
  label: string;
  detail?: string | null;
  tool_call?: ToolCall | null;
  status?: string;
  timestamp?: string | null;
  data_source?: DataSource | null;
}

/**
 * A single leg of a route (API_CONTRACTS §3). The backend serializes origin/destination under
 * the `from`/`to` aliases. Legs were declared in A3 but stayed empty; **A7 populates them** with
 * the recommended route's leg detail from the mock `get_route_details` tool, so they are still
 * `data_source: mock` — simulated structure, never a live timetable or a real seat.
 */
export interface Leg {
  id: string;
  mode: string; // walk | tuk | bus | train | taxi | ferry
  from: string;
  to: string;
  departure_time?: string | null;
  arrival_time?: string | null;
  duration_min?: number | null;
  fare_lkr?: number | null;
  walking_km?: number | null;
  delay_risk?: string | null; // none | low | moderate | high
  delay_min_estimate?: number | null;
  notes?: string | null;
  data_source?: DataSource;
}

/**
 * A single structured hard-constraint failure (A6 §5), mirroring the backend
 * `ConstraintViolation`. Surfaced on a `Recommendation` so the UI can explain *why* a route was
 * excluded instead of silently dropping it. `type` is a stable uppercase code; `message` is
 * concise and grounded in the actual candidate/request values (A6 §14).
 */
export interface ConstraintViolation {
  /** Stable code: ORIGIN | DESTINATION | BUDGET | ARRIVAL_DEADLINE | AVAILABILITY. */
  type: string;
  /** Concise, grounded human explanation of the failure. */
  message: string;
}

/**
 * A recommended (or alternative) route (API_CONTRACTS §3), populated by the A3 decision engine.
 * `rationale` is the headline reason; `reasons` is the concise, observable list of decision
 * factors (A3 brief §8/§14.6); `trade_offs` explains why an alternative ranked lower. Every
 * figure is MOCK in A3 (`data_source`), never live transit data.
 *
 * A6 refines the decision engine and adds four additive, optional route-comparison fields
 * (`rank`, `valid`, `strengths`, `constraint_violations`). They may be absent on older responses,
 * so the UI renders them only when present — the A3 contract is preserved.
 */
export interface Recommendation {
  id: string;
  summary: string;
  total_duration_min?: number | null;
  total_fare_lkr?: number | null;
  transfers?: number | null;
  walking_km?: number | null;
  within_budget?: boolean | null;
  delay_risk?: string | null;
  score?: number | null;
  rationale?: string | null;
  reasons?: string[];
  trade_offs?: string[];
  /** A6 additive: 1-based rank among VALID candidates; absent/null when excluded. */
  rank?: number | null;
  /** A6 additive: true when every hard constraint passed; false when excluded. */
  valid?: boolean | null;
  /** A6 additive: major grounded strengths for route comparison (§11). */
  strengths?: string[];
  /** A6 additive: structured hard-constraint failures (§5); empty when valid. */
  constraint_violations?: ConstraintViolation[];
  is_recommended?: boolean;
  data_source?: DataSource;
}

/**
 * POST /api/route/plan response (API_CONTRACTS §2).
 * A3: `status` is COMPLETED with a mock `recommendation`, `alternatives`, the full
 * `agent_actions` trace, and a concise `reasoning` when the request can be planned; it stays
 * UNDERSTANDING with no recommendation when clarification is required.
 *
 * **A7 changes no field.** `legs` now carries the recommended route's leg detail, and
 * `agent_actions` may hold several tool calls (search + fare + delay + details) in a
 * planner-selected order — all still `data_source: mock`.
 */
export interface PlanResponse {
  status: AgentState;
  request?: TravelRequest | null;
  recommendation?: Recommendation | null;
  legs?: Leg[];
  alternatives?: Recommendation[];
  agent_actions: AgentAction[];
  reasoning?: string | null;
}
