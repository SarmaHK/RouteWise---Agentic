/**
 * Shared domain types mirroring docs/API_CONTRACTS.md (A1 foundation + A2 TravelRequest).
 *
 * Contract-first: these mirror the backend `schemas/` and API_CONTRACTS.md. The FULL domain
 * types (detailed route/leg/recommendation shapes) are expanded in A8; A1 defines only what
 * the foundation shell + API client need. Keep in sync — do not diverge (types/README.md).
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

/** One entry of the agent-activity log (API_CONTRACTS §4). */
export interface AgentAction {
  seq: number;
  state: AgentState;
  label: string;
  detail?: string | null;
  status?: string;
  timestamp?: string | null;
  data_source?: DataSource | null;
}

/**
 * POST /api/route/plan response (API_CONTRACTS §2).
 * A2: `request` is the understood TravelRequest and `status` is UNDERSTANDING;
 * `recommendation`/`legs`/`alternatives` stay empty (loosely typed) until real planning in A3+/A8.
 */
export interface PlanResponse {
  status: AgentState;
  request?: TravelRequest | null;
  recommendation?: Record<string, unknown> | null;
  legs?: Record<string, unknown>[];
  alternatives?: Record<string, unknown>[];
  agent_actions: AgentAction[];
}
