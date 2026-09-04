/**
 * `POST /api/route/plan` — the reserved primary endpoint (API_CONTRACTS §2).
 *
 * In A3 the backend UNDERSTANDS the request (A2 natural-language extraction into a TravelRequest)
 * and, when no clarification is needed, runs the agent to a decision: it returns status COMPLETED
 * with a MOCK recommendation, alternatives, the agent-action trace, and a concise `reasoning`.
 * When a hard constraint is missing it stops early (status UNDERSTANDING) and returns the
 * clarification. This module is the single caller of that endpoint — components never fetch it
 * directly (ARCHITECTURE §3.2).
 */

import type { PlanRequest, PlanResponse } from '../../types/api';
import { request } from './client';

/** Submit a travel request; returns the agent's plan response (A3: understanding → decision). */
export function planRoute(payload: PlanRequest): Promise<PlanResponse> {
  return request<PlanResponse>('/api/route/plan', { method: 'POST', body: payload });
}
