/**
 * Shared domain types mirroring docs/API_CONTRACTS.md (Phase A1 foundation subset).
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

/** POST /api/route/plan request (API_CONTRACTS §2). */
export interface PlanRequest {
  origin: string;
  destination: string;
  budget?: number | null;
  luggage?: string | null;
  walking_preference?: string | null;
  departure_time?: string | null;
  arrival_deadline?: string | null;
  preferences?: Record<string, unknown>;
  raw_text?: string | null;
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
 * Foundation: `recommendation`/`legs`/`alternatives` are loosely typed (A1 returns a stub);
 * they are strongly typed in A8 when real planning lands.
 */
export interface PlanResponse {
  status: AgentState;
  request?: PlanRequest | null;
  recommendation?: Record<string, unknown> | null;
  legs?: Record<string, unknown>[];
  alternatives?: Record<string, unknown>[];
  agent_actions: AgentAction[];
}
